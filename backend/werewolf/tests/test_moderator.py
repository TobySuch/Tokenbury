import itertools
import json
from collections import Counter

import pytest

from werewolf.agents import ScriptedAgent
from werewolf.events import append_event
from werewolf.models import ENGINE, PUBLIC, WOLF_CHAT, AgentCall, Game, GameEvent
from werewolf.moderator import (
    END_TOOL,
    PICK_TOOL,
    build_moderator_prompt,
    discussion_state,
    eligible_speakers,
    fallback_pick,
    forced_end_reason,
    moderate,
    moderator_prompt_for,
    moderator_tools,
)
from werewolf.tests.factories import create_classic_game, make_characters
from werewolf.tests.helpers import simulate_discussion
from werewolf.turns import BudgetExceeded

pytestmark = pytest.mark.django_db


def build(config=None, seed=3):
    make_characters()
    game = create_classic_game(seed=seed)
    game.phase = Game.Phase.DISCUSSION
    game.day_number = 1
    game.config = config or {}
    game.save()
    return game


@pytest.fixture
def game():
    return build()


def players(game):
    return list(game.players.all())


def say(game, player, message="hi"):
    return append_event(
        game,
        type="speech",
        visibility=PUBLIC,
        actor=player,
        payload={"message": message},
    )


def do_pass(game, player):
    return append_event(
        game,
        type="pass",
        visibility=ENGINE,
        actor=player,
        payload={"phase": "discussion"},
    )


def pick(name, reason="because"):
    return [("pick_speaker", {"name": name, "reason": reason})]


def end(reason="done"):
    return [("end_discussion", {"reason": reason})]


def agent_of(*steps):
    return ScriptedAgent(list(steps))


class Boom:
    def respond(self, messages, tools):
        raise RuntimeError("down")


def picks_events(game):
    return list(GameEvent.objects.filter(game=game, type="moderator_pick"))


# ---- state ----


def test_state_empty(game):
    s = discussion_state(game)
    assert s.messages_used == 0 and s.last_speaker_id is None and not s.ended
    assert s.per_player == {} and s.declined == [] and s.picks == []


def test_state_derivation(game):
    a, b, c = players(game)[:3]
    say(game, a)
    say(game, b)
    do_pass(game, c)
    s = discussion_state(game)
    assert s.messages_used == 2
    assert s.per_player == {a.id: 1, b.id: 1}
    assert s.last_speaker_id == b.id
    assert s.consecutive_passes == 1 and s.declined == [c.id]
    say(game, c)
    s = discussion_state(game)
    assert s.consecutive_passes == 0 and s.declined == []


def test_state_ignores_other_days_and_phases(game):
    a = players(game)[0]
    append_event(game, type="speech", visibility=PUBLIC, actor=a, day=0, payload={})
    append_event(
        game, type="pass", visibility=ENGINE, actor=a, phase="vote", payload={}
    )
    s = discussion_state(game)
    assert s.messages_used == 0 and s.consecutive_passes == 0


def test_state_rebuilds_after_resume(game):
    ps = players(game)
    moderate(game, agent_of(pick(ps[0].name)), discussion_state(game))
    say(game, ps[0])
    first = discussion_state(game)
    again = discussion_state(Game.objects.get(pk=game.pk))
    assert first == again
    assert len(first.picks) == 1 and first.picks[0]["pick_id"] == ps[0].id


# ---- eligibility / forced end ----


def test_eligible_excludes_dead_last_and_capped(game):
    ps = players(game)
    ps[0].alive = False
    ps[0].save()
    for _ in range(6):
        say(game, ps[1])
        say(game, ps[2])
    say(game, ps[3])
    s = discussion_state(game)
    names = [p.id for p in eligible_speakers(game, s)]
    assert ps[0].id not in names  # dead
    assert ps[1].id not in names  # capped
    assert ps[2].id not in names  # capped
    assert ps[3].id not in names  # last speaker
    assert names == [p.id for p in ps[4:]]  # seat order


def test_forced_end_reasons(game):
    ps = players(game)
    assert forced_end_reason(game, discussion_state(game)) is None
    for _ in range(3):
        do_pass(game, ps[0])
    assert forced_end_reason(game, discussion_state(game)) == "passes"


def test_forced_end_cap():
    game = build({"discussion_max_messages": 3, "discussion_max_per_player": 6})
    ps = players(game)
    for p in ps[:3]:
        say(game, p)
    assert forced_end_reason(game, discussion_state(game)) == "cap"


def test_forced_end_no_eligible():
    game = build({"discussion_max_per_player": 1})
    for p in players(game):
        say(game, p)
    assert forced_end_reason(game, discussion_state(game)) == "no_eligible"


# ---- moderate ----


def test_llm_pick_accepted_case_insensitive(game):
    target = players(game)[2]
    payload = moderate(
        game, agent_of(pick(target.name.upper(), "addressed")), discussion_state(game)
    )
    assert payload == {
        "pick_id": target.id,
        "end": False,
        "reason": "addressed",
        "source": "llm",
    }
    (event,) = picks_events(game)
    assert event.visibility == ENGINE and event.actor is None
    assert event.payload == payload
    assert AgentCall.objects.filter(game=game, player=None).count() == 1


@pytest.mark.parametrize("why", ["dead", "capped", "last"])
def test_ineligible_llm_pick_falls_back(game, why):
    ps = players(game)
    target = ps[2]
    if why == "dead":
        target.alive = False
        target.save()
    elif why == "capped":
        for _ in range(6):
            say(game, target)
            say(game, ps[3])
        say(game, ps[4])
    else:
        say(game, target)
    state = discussion_state(game)
    payload = moderate(game, agent_of(pick(target.name)), state)
    assert payload["source"] == "fallback"
    assert payload["pick_id"] != target.id
    assert payload["pick_id"] in [p.id for p in eligible_speakers(game, state)]
    assert "fallback" in payload["reason"]


def test_unknown_name_and_no_tool_fall_back(game):
    p1 = moderate(game, agent_of(pick("Nobody")), discussion_state(game))
    assert p1["source"] == "fallback" and "Nobody" in p1["reason"]
    p2 = moderate(game, agent_of([]), discussion_state(game))
    assert p2["source"] == "fallback"
    p3 = moderate(
        game, agent_of([("pick_speaker", {"reason": "x"})]), discussion_state(game)
    )
    assert p3["source"] == "fallback"


def test_failed_call_falls_back_and_logs(game):
    payload = moderate(game, Boom(), discussion_state(game))
    assert payload["source"] == "fallback" and payload["pick_id"] is not None
    call = AgentCall.objects.get(game=game)
    assert call.player is None and "error" in json.loads(call.response)


def test_end_refused_before_min(game):
    payload = moderate(game, agent_of(end()), discussion_state(game))
    assert payload["end"] is False and payload["source"] == "fallback"
    assert payload["pick_id"] is not None


def test_end_accepted_at_min(game):
    ps = players(game)
    for i in range(6):
        say(game, ps[i % 2])
    payload = moderate(game, agent_of(end("run its course")), discussion_state(game))
    assert payload == {
        "pick_id": None,
        "end": True,
        "reason": "run its course",
        "source": "llm",
    }
    assert discussion_state(game).ended


def test_forced_end_makes_no_call():
    game = build({"discussion_max_messages": 2})
    ps = players(game)
    say(game, ps[0])
    say(game, ps[1])
    payload = moderate(game, Boom(), discussion_state(game))
    assert payload == {
        "pick_id": None,
        "end": True,
        "reason": "cap",
        "source": "forced",
    }
    assert AgentCall.objects.filter(game=game).count() == 0
    assert picks_events(game)[0].visibility == ENGINE


def test_budget_exceeded_propagates():
    game = build({"call_budget": 0})
    with pytest.raises(BudgetExceeded):
        moderate(game, agent_of(pick("x")), discussion_state(game))


def test_tools_schemas():
    names = [t["function"]["name"] for t in moderator_tools()]
    assert names == [PICK_TOOL, END_TOOL]


# ---- simulated loop ----


def test_three_passes_in_a_row_end_discussion(game):
    ps = players(game)
    ps_iter = iter(ps)
    agent = ScriptedAgent(lambda m, t: pick(next(ps_iter).name))
    log = simulate_discussion(game, agent, ["pass", "pass", "pass"])
    assert log[-1]["end"] and log[-1]["reason"] == "passes"
    assert discussion_state(game).ended


def test_caps_hold_over_full_loop():
    game = build({"discussion_max_messages": 12, "discussion_max_per_player": 2})
    log = simulate_discussion(game, Boom(), ["speech"] * 100)
    s = discussion_state(game)
    assert s.messages_used <= 12
    assert max(s.per_player.values()) <= 2
    assert log[-1]["end"]
    # nobody picked twice in a row
    picked = [p["pick_id"] for p in log if not p["end"]]
    assert all(a != b for a, b in itertools.pairwise(picked))


# ---- fallback weighting ----


def test_fallback_deterministic(game):
    state = discussion_state(game)
    el = eligible_speakers(game, state)
    assert fallback_pick(game, state, el) == fallback_pick(game, state, el)


def test_fallback_follows_talkativeness():
    game = build()
    counts = Counter()
    for seed in range(2000):
        game.seed = seed
        state = discussion_state(game)
        chosen = fallback_pick(game, state, eligible_speakers(game, state))
        counts[chosen.character.talkativeness] += 1
    # 7 players: talkativeness 1..5 with 1 and 2 doubled
    per_player = {
        t: counts[t] / sum(1 for p in players(game) if p.character.talkativeness == t)
        for t in range(1, 6)
    }
    assert per_player[5] > per_player[3] > per_player[1]
    assert per_player[5] / per_player[1] == pytest.approx(5, rel=0.3)
    assert per_player[3] / per_player[1] == pytest.approx(3, rel=0.3)


# ---- prompt ----


def test_prompt_pure_function_contents():
    msgs = build_moderator_prompt(
        roster_rows=[
            {"name": "Ann", "alive": True, "talkativeness": 4, "messages": 2},
            {"name": "Bob", "alive": False, "talkativeness": 1, "messages": 0},
        ],
        recent_messages=["Ann: hello there"],
        prior_picks=[("Ann", "addressed"), ("END", "enough")],
        declined_names=["Cy"],
        stopwatch={"used": 3, "max": 30, "min": 6},
        eligible_names=["Cy", "Dee"],
    )
    text = "\n".join(m["content"] for m in msgs)
    for needle in [
        "Ann: hello there",
        "3 of 30",
        "6",
        "Cy",
        "Dee",
        "addressed",
        "END",
        "Bob",
    ]:
        assert needle in text
    assert msgs[0]["role"] == "system"


def test_moderator_view_has_no_secrets(game):
    ps = players(game)
    canaries = {
        "NOTE_CANARY": None,
        "WOLFCHAT_CANARY": None,
        "VOTE_CANARY": None,
        "ENGINE_CANARY": None,
        "PRIVATE_CANARY": None,
    }
    wolf = next(p for p in ps if p.role == "wolf")
    append_event(
        game,
        type="role_assigned",
        visibility=f"player:{wolf.id}",
        actor=wolf,
        payload={"note": "PRIVATE_CANARY"},
        phase="setup",
        day=0,
    )
    append_event(
        game,
        type="wolf_message",
        visibility=WOLF_CHAT,
        actor=wolf,
        payload={"message": "WOLFCHAT_CANARY"},
    )
    append_event(
        game,
        type="vote_cast",
        visibility=ENGINE,
        actor=wolf,
        payload={"target_id": ps[1].id, "x": "VOTE_CANARY"},
    )
    append_event(
        game,
        type="phase_change",
        visibility=ENGINE,
        payload={"from": "a", "to": "ENGINE_CANARY"},
    )
    from werewolf.models import PlayerNotes

    PlayerNotes.objects.create(
        game=game, player=wolf, version=99, text="NOTE_CANARY", at_seq=1
    )
    say(game, ps[0], "public line one")
    do_pass(game, ps[1])
    moderate(game, agent_of(pick(ps[2].name, "my reason")), discussion_state(game))
    state = discussion_state(game)
    messages = moderator_prompt_for(game, state)
    text = "\n".join(m["content"] for m in messages)
    for canary in canaries:
        assert canary not in text
    lowered = text.lower()
    for word in ["wolf", "seer", "villager", "werewolf"]:
        assert word not in lowered
    assert "public line one" in text
    assert "my reason" in text
    assert ps[1].name in text  # declined


# ---- declined players ----


def test_fallback_pick_skips_players_who_declined(game):
    a, b = players(game)[:2]
    for n in range(20):
        state = discussion_state(game)
        state.declined = [a.id]
        state.picks = [{}] * n
        assert fallback_pick(game, state, [a, b]) == b


def test_fallback_pick_uses_declined_when_nobody_else_is_left(game):
    a = players(game)[0]
    state = discussion_state(game)
    state.declined = [a.id]
    assert fallback_pick(game, state, [a]) == a


def test_llm_pick_of_declined_player_falls_back(game):
    ps = players(game)
    do_pass(game, ps[1])
    moderate(game, agent_of(pick(ps[1].name)), discussion_state(game))
    (event,) = picks_events(game)
    assert event.payload["source"] == "fallback"
    assert event.payload["pick_id"] != ps[1].id
