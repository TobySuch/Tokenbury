import json
from dataclasses import replace

import pytest

from simulation.llm import LLMError
from werewolf.agents import ReplayAgent, ScriptedAgent
from werewolf.models import AgentCall, Game, PlayerNotes
from werewolf.notes import current_notes
from werewolf.prompts import Turn
from werewolf.tests.factories import create_classic_game, make_characters
from werewolf.tools import ValidationContext
from werewolf.turns import (
    BudgetExceeded,
    TurnResult,
    check_budget,
    recorded_responses,
    run_turn,
)

pytestmark = pytest.mark.django_db

SPEAK = ("speak", {"message": "hello"})
BAD_SPEAK = ("speak", {"message": ""})
PASS = ("pass", {})


def build(config=None, seed=3):
    make_characters()
    game = create_classic_game(seed=seed)
    if config:
        game.config = config
        game.save()
    return game


@pytest.fixture
def game():
    return build()


def ctx_for(game, player, kind="discussion", **overrides):
    wolves = [p for p in game.players.all() if p.role == "wolf"]
    ctx = ValidationContext(
        turn_kind=kind,
        actor_role=player.role,
        actor_alive=player.alive,
        wolf_names=[w.name for w in wolves],
        living_names=[p.name for p in game.players.filter(alive=True)],
        living_non_wolf_names=[
            p.name for p in game.players.filter(alive=True) if p.role != "wolf"
        ],
        speech_max_chars=400,
        actor_name=player.name,
    )
    return replace(ctx, **overrides)


def turn_for(kind="discussion"):
    return Turn(phase=kind, day=1, kind=kind)


def run(game, player, script, kind="discussion", **ctx_overrides):
    agent = ScriptedAgent(script)
    return run_turn(
        game,
        player,
        agent,
        turn_for(kind),
        ctx_for(game, player, kind, **ctx_overrides),
        [{"role": "user", "content": "go"}],
    )


def villager(game):
    return game.players.filter(role="villager").first()


def test_valid_speak_first_try(game):
    p = villager(game)
    result = run(game, p, [[SPEAK]])
    assert result == TurnResult("speak", {"message": "hello"}, fallback=False)
    assert AgentCall.objects.filter(game=game).count() == 1


def test_notes_then_speak_in_one_response(game):
    p = villager(game)
    result = run(game, p, [[("append_note", {"text": "n1"}), SPEAK]])
    assert result.action == "speak"
    assert current_notes(p) == "n1"
    assert PlayerNotes.objects.get(player=p).version == 1


def test_notes_after_terminal_call_are_still_saved(game):
    p = villager(game)
    result = run(game, p, [[PASS, ("append_note", {"text": "late"})]])
    assert result.action == "pass"
    assert current_notes(p) == "late"


def test_notes_around_invalid_terminal_are_all_saved(game):
    p = villager(game)
    script = [
        [BAD_SPEAK, ("append_note", {"text": "after"})],
        [("append_note", {"text": "before"}), SPEAK],
    ]
    result = run(game, p, script)
    assert result.action == "speak"
    assert current_notes(p) == "after\nbefore"


def test_duplicate_append_note_in_one_turn_is_not_rewritten(game):
    p = villager(game)
    note = ("append_note", {"text": "same"})
    result = run(game, p, [[note, BAD_SPEAK], [note, SPEAK]])
    assert result.action == "speak"
    assert current_notes(p) == "same"
    assert PlayerNotes.objects.get(player=p).version == 1


def test_duplicate_append_note_reports_already_saved(game):
    p = villager(game)
    note = ("append_note", {"text": "same"})
    seen = []

    def script(messages, tools):
        seen.append(list(messages))
        return [note, BAD_SPEAK] if len(seen) < 3 else [SPEAK]

    run(game, p, script)
    tool_texts = [m["content"] for m in seen[2] if m["role"] == "tool"]
    assert any("already saved" in t for t in tool_texts)


def test_note_call_limit(game):
    p = villager(game)
    calls = [("append_note", {"text": f"n{i}"}) for i in range(5)] + [SPEAK]
    result = run(game, p, [calls])
    assert result.action == "speak"
    assert current_notes(p) == "n0\nn1\nn2\nn3"


def test_note_limit_error_text_and_counts_across_retries(game):
    p = villager(game)
    seen = []

    def script(messages, tools):
        seen.append(messages)
        if len(seen) == 1:
            return [("append_note", {"text": f"a{i}"}) for i in range(3)]
        if len(seen) == 2:
            return [("append_note", {"text": f"b{i}"}) for i in range(2)]
        return [SPEAK]

    run(game, p, script)
    tool_msgs = [m for m in seen[2] if m["role"] == "tool"]
    assert "note call limit reached" in tool_msgs[-1]["content"]
    assert current_notes(p).count("\n") == 3  # 4 notes written


def test_invalid_then_valid_retry_carries_error_tool_result(game):
    p = villager(game)
    seen = []

    def script(messages, tools):
        seen.append(list(messages))
        return [BAD_SPEAK] if len(seen) == 1 else [SPEAK]

    result = run(game, p, script)
    assert result.action == "speak" and not result.fallback
    second = seen[1]
    assert second[-2]["role"] == "assistant"
    tool_msg = second[-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == second[-2]["tool_calls"][0]["id"]
    assert "non-empty" in tool_msg["content"]


def test_three_invalid_falls_back_to_pass(game):
    p = villager(game)
    result = run(game, p, [[BAD_SPEAK]] * 3)
    assert result == TurnResult("pass", {}, fallback=True)
    assert AgentCall.objects.filter(game=game).count() == 3


def test_vote_fallback_is_none(game):
    p = villager(game)
    bad = [("vote", {"target": "Nobody"})]
    result = run(game, p, [bad] * 3, kind="vote")
    assert result == TurnResult("vote", {"target": "none"}, fallback=True)


def test_valid_vote(game):
    p = villager(game)
    target = game.players.exclude(pk=p.pk).first().name
    result = run(game, p, [[("vote", {"target": target})]], kind="vote")
    assert result.action == "vote" and result.args == {"target": target}


def test_no_tool_calls_gets_nudge_then_recovers(game):
    p = villager(game)
    seen = []

    def script(messages, tools):
        seen.append(list(messages))
        return [] if len(seen) == 1 else [PASS]

    result = run(game, p, script)
    assert result.action == "pass" and not result.fallback
    assert seen[1][-1]["role"] == "user"
    assert "tool" in seen[1][-1]["content"].lower()


def test_unparseable_arguments_is_error(game):
    from werewolf.agents import AgentResponse, ToolCall

    p = villager(game)
    bad = AgentResponse(
        [ToolCall("x", "speak", None, "{oops")],
        "",
        0,
        0,
        {"role": "assistant", "tool_calls": []},
    )

    class Agent:
        def respond(self, messages, tools):
            return bad

    result = run_turn(
        game,
        p,
        Agent(),
        turn_for(),
        ctx_for(game, p),
        [{"role": "user", "content": "x"}],
    )
    assert result.fallback


def test_agent_exceptions_retry_then_fallback(game):
    p = villager(game)

    class Boom:
        def respond(self, messages, tools):
            raise LLMError("kaput")

    result = run_turn(
        game,
        p,
        Boom(),
        turn_for(),
        ctx_for(game, p),
        [{"role": "user", "content": "x"}],
    )
    assert result == TurnResult("pass", {}, fallback=True)
    calls = list(AgentCall.objects.filter(game=game))
    assert len(calls) == 3
    assert all("kaput" in c.response for c in calls)
    assert all(c.tokens_in == 0 and c.tokens_out == 0 for c in calls)


def test_arbitrary_exception_then_success(game):
    p = villager(game)
    inner = ScriptedAgent([[SPEAK]])
    state = {"n": 0}

    class Flaky:
        def respond(self, messages, tools):
            state["n"] += 1
            if state["n"] == 1:
                raise ValueError("weird")
            return inner.respond(messages, tools)

    result = run_turn(
        game,
        p,
        Flaky(),
        turn_for(),
        ctx_for(game, p),
        [{"role": "user", "content": "x"}],
    )
    assert result.action == "speak" and not result.fallback


def test_notes_error_surfaces_as_tool_error(game):
    p = villager(game)
    game.config = {"notes_max_chars": 5}
    game.save()
    seen = []

    def script(messages, tools):
        seen.append(list(messages))
        if len(seen) == 1:
            return [("append_note", {"text": "way too long for the cap"})]
        return [SPEAK]

    result = run(game, p, script)
    assert result.action == "speak"
    assert "too long" in seen[1][-1]["content"].lower()
    assert current_notes(p) == ""


def test_every_call_logged(game):
    p = villager(game)
    run(game, p, [[BAD_SPEAK], [SPEAK]])
    calls = list(AgentCall.objects.filter(game=game))
    assert len(calls) == 2
    assert all(c.player == p and c.latency_ms >= 0 for c in calls)
    assert json.loads(calls[0].prompt)[0]["content"] == "go"
    logged = json.loads(calls[1].response)
    assert logged["tool_calls"][0]["name"] == "speak"
    assert "raw_arguments" in logged["tool_calls"][0]


def test_tokens_logged(game):
    from werewolf.agents import AgentResponse, ToolCall

    p = villager(game)
    resp = AgentResponse(
        [ToolCall("i", "pass", {}, "{}")], "", 12, 3, {"role": "assistant"}
    )

    class Agent:
        def respond(self, messages, tools):
            return resp

    run_turn(game, p, Agent(), turn_for(), ctx_for(game, p), [])
    call = AgentCall.objects.get(game=game)
    assert (call.tokens_in, call.tokens_out) == (12, 3)


def test_budget_aborts_game_on_third_call():
    game = build({"call_budget": 2})
    p = villager(game)
    with pytest.raises(BudgetExceeded):
        run(game, p, [[BAD_SPEAK]] * 3)
    game.refresh_from_db()
    assert game.status == Game.Status.ABORTED
    assert AgentCall.objects.filter(game=game).count() == 2


def test_check_budget_ok_below_limit(game):
    check_budget(game)
    game.refresh_from_db()
    assert game.status == Game.Status.ACTIVE


def test_actor_name_defaults_from_player_for_self_vote(game):
    p = villager(game)
    result = run(
        game,
        p,
        [[("vote", {"target": p.name})]] * 3,
        kind="vote",
        actor_name="",
    )
    assert result.fallback


def _wolf(game):
    return game.players.filter(role="wolf").first()


def _two_names(game, p):
    return [x.name for x in game.players.exclude(pk=p.pk)][:2]


def _invalid_cases():
    return {
        "wrong_phase": ("discussion", lambda g, p: ("vote", {"target": "none"}), {}),
        "unknown_tool": ("discussion", lambda g, p: ("shout", {}), {}),
        "over_cap": ("discussion", lambda g, p: ("speak", {"message": "x" * 401}), {}),
        "empty_message": ("discussion", lambda g, p: ("speak", {"message": " "}), {}),
        "unknown_target": ("vote", lambda g, p: ("vote", {"target": "Zed"}), {}),
        "self_vote": ("vote", lambda g, p: ("vote", {"target": p.name}), {}),
        "dead_target": ("vote", "dead", {}),
        "dead_actor": (
            "discussion",
            lambda g, p: SPEAK,
            {"actor_alive": False},
        ),
        "wolf_names_wolf": ("wolf_chat", "wolfname", {}),
        "wolf_bad_kill_target": ("wolf_chat", "wolfkill", {}),
        "seer_speaks_at_night": ("seer_notes", "seerspeak", {}),
    }


@pytest.mark.parametrize("case", list(_invalid_cases()))
def test_invalid_call_retries_twice_then_falls_back(game, case):
    kind, call, overrides = _invalid_cases()[case]
    if case == "dead_target":
        victim = game.players.filter(role="villager").last()
        victim.alive = False
        victim.save()
        actor = game.players.filter(role="villager", alive=True).first()
        call = ("vote", {"target": victim.name})
    elif case == "wolf_names_wolf":
        actor = _wolf(game)
        call = ("speak", {"message": f"let's get {actor.name}"})
    elif case == "wolf_bad_kill_target":
        actor = _wolf(game)
        call = ("speak", {"message": "hm", "kill_target": actor.name})
    elif case == "seer_speaks_at_night":
        actor = game.players.get(role="seer")
        call = ("speak", {"message": "I see"})
    else:
        actor = villager(game)
        call = call(game, actor)
    result = run(game, actor, [[call]] * 3, kind=kind, **overrides)
    assert result.fallback
    assert AgentCall.objects.filter(game=game).count() == 3
    assert result.action == ("vote" if kind == "vote" else "pass")


def test_replay_reproduces_turn_results():
    game_a = build()
    game_b = create_classic_game(seed=3)

    def play(game, agent_for):
        p = villager(game)
        v = game.players.exclude(pk=p.pk).first().name
        steps = [
            ("discussion", [[("append_note", {"text": "x"}), SPEAK]]),
            ("discussion", [[BAD_SPEAK]] * 3),
            ("vote", [[("vote", {"target": v})]]),
            ("discussion", "error"),
        ]
        results = []
        for kind, script in steps:
            agent = agent_for(script)
            results.append(
                run_turn(
                    game,
                    p,
                    agent,
                    turn_for(kind),
                    ctx_for(game, p, kind),
                    [{"role": "user", "content": "go"}],
                )
            )
        return results

    class Boom:
        def respond(self, messages, tools):
            raise LLMError("net down")

    original = play(
        game_a, lambda script: Boom() if script == "error" else ScriptedAgent(script)
    )
    assert original[-1].fallback

    replay_agent = ReplayAgent(recorded_responses(game_a))
    replayed = play(game_b, lambda script: replay_agent)

    assert replayed == original
    assert current_notes(villager(game_b)) == current_notes(villager(game_a)) == "x"
    assert (
        AgentCall.objects.filter(game=game_b).count()
        == AgentCall.objects.filter(game=game_a).count()
    )
