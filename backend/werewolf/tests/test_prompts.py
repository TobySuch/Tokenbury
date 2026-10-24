import pytest

from werewolf.events import append_event
from werewolf.models import ENGINE, PUBLIC, WOLF_CHAT, Player, player_visibility
from werewolf.notes import append_note
from werewolf.prompts import (
    PERSONA_LINES,
    PlayerView,
    Turn,
    build_player_prompt,
    build_prompt_for,
    player_view,
    render_event,
)
from werewolf.setup import create_game
from werewolf.tests.factories import make_characters
from werewolf.visibility import RosterEntry, VisibleEvent

pytestmark = pytest.mark.django_db

KINDS = ["wolf_chat", "seer_notes", "discussion", "vote", "day_notes"]
HEADINGS = [
    "## Rules and role",
    "## Who you are",
    "## Players",
    "## What you can see (today)",
    "## Your private notes (only you can see these)",
    "## Your turn",
]


def turn(kind="discussion", **kw):
    return Turn(
        phase="discussion", day=1, kind=kind, allowed_tools=["speak", "pass"], **kw
    )


def view(role="villager", talk=3, **kw):
    base = {
        "player_id": 1,
        "name": "Alice",
        "role": role,
        "talkativeness": talk,
        "win_condition": "Win when every wolf has been eliminated.",
        "wolf_label": None,
        "teammate_name": None,
        "teammate_label": None,
    }
    base.update(kw)
    return PlayerView(**base)


def text(messages):
    return "\n".join(m["content"] for m in messages)


def build(v=None, events=(), notes="", roster=(), t=None, reveal=True):
    return build_player_prompt(
        v or view(), list(events), notes, list(roster), t or turn(), 3000, reveal
    )


def ev(type, payload=None, speaker=None, day=1, seq=1):
    return VisibleEvent(seq, day, "x", type, speaker, payload or {})


def test_sections_in_order():
    t = text(build(notes="n"))
    positions = [t.index(h) for h in HEADINGS]
    assert positions == sorted(positions)


def test_messages_shape_and_stable_prefix():
    a = build(notes="one", events=[ev("speech", {"message": "hi"}, "Bob")])
    b = build(notes="two", events=[ev("speech", {"message": "hi"}, "Bob")])
    assert a[0]["role"] == "system"
    assert a[0] == b[0]
    assert "private notes" not in a[0]["content"]


@pytest.mark.parametrize("talk", [1, 2, 3, 4, 5])
def test_persona_line_varies(talk):
    t = text(build(view(talk=talk)))
    assert PERSONA_LINES[talk] in t
    assert "Alice" in t
    for other, line in PERSONA_LINES.items():
        if other != talk:
            assert line not in t


def test_notes_usage_line():
    assert "12 / 3000 characters used" in text(build(notes="x" * 12))
    assert "0 / 3000 characters used" in text(build())


def test_wolf_sees_teammate_and_labels():
    v = view(
        "wolf",
        wolf_label="Wolf A",
        teammate_name="Wanda",
        teammate_label="Wolf B",
    )
    t = text(build(v))
    assert "Wanda" in t
    assert "Wolf A" in t
    assert "Wolf B" in t
    assert "do not name yourself or your teammate" in t


def test_role_specific_guidance_only_to_that_role():
    wolf = text(build(view("wolf", teammate_name="W", teammate_label="Wolf B")))
    seer = text(build(view("seer")))
    vill = text(build(view("villager")))
    assert "do not name yourself or your teammate" not in seer + vill
    assert "Work out who the wolves are from how they talk" in seer
    assert "Work out who the wolves are from how they talk" not in wolf + vill
    for t in (wolf, seer, vill):
        assert "seer may be listening" in t
        assert "Reason independently" in t
        assert "only today" in t


def test_roster_roles_only_for_dead_when_flag_on():
    roster = [RosterEntry("Bob", True, None), RosterEntry("Cara", False, "wolf")]
    on = text(build(roster=roster, reveal=True))
    assert "Bob (alive)" in on
    assert "Cara (dead, was a wolf)" in on
    off = text(build(roster=[RosterEntry("Cara", False, None)], reveal=False))
    assert "Cara (dead)" in off
    assert "was a" not in off.split("## What you can see")[0].split("## Players")[1]


def test_log_oldest_first():
    t = text(
        build(
            events=[
                ev("speech", {"message": "first"}, "Bob", seq=1),
                ev("speech", {"message": "second"}, "Cara", seq=2),
            ]
        )
    )
    assert t.index("first") < t.index("second")


def test_turn_instruction():
    t = text(build(t=turn(extra="The moderator has invited you to speak.")))
    after = t.split("## Your turn")[1]
    assert "discussion" in after
    assert "speak" in after
    assert "pass" in after
    assert "invited you to speak" in after
    assert "notes" in after


def test_render_event_each_type():
    assert (
        render_event(
            ev(
                "wolf_message",
                {"message": "Hello", "kill_target": "Dorothy"},
                "Wolf A",
            )
        )
        == "[Night] Wolf A: Hello (suggests killing Dorothy)"
    )
    assert render_event(
        ev("wolf_message", {"message": "Hi", "kill_target": None}, "Wolf B")
    ) == ("[Night] Wolf B: Hi")
    assert "Dorothy" in render_event(
        ev("wolf_target", {"target": "Dorothy", "source": "agreed"})
    )
    assert render_event(ev("speech", {"message": "Hey"}, "Margaret")) == "Margaret: Hey"
    night = render_event(
        ev("death", {"player": "Dorothy", "cause": "night_kill", "role": "villager"})
    )
    assert night == "Dorothy was killed in the night. They were a villager."
    assert "eliminated" in render_event(
        ev("death", {"player": "Bob", "cause": "vote", "role": "wolf"})
    )
    assert "They were" not in render_event(
        ev("death", {"player": "Bob", "cause": "vote"})
    )
    res = render_event(
        ev(
            "vote_result",
            {
                "votes": [
                    {"voter": "A", "target": "B"},
                    {"voter": "B", "target": None},
                ],
                "tally": {"B": 1, "none": 1},
                "eliminated": None,
            },
        )
    )
    assert "A voted for B" in res
    assert "B voted for no one" in res
    assert "B: 1" in res
    assert "No one was eliminated." in res
    counts = render_event(
        ev("vote_result", {"votes": [], "tally": {"B": 3}, "eliminated": "B"})
    )
    assert "B: 3" in counts
    assert "B was eliminated" in counts
    assert "town" in render_event(ev("game_over", {"winner": "town"})).lower()
    assert "wolf" in render_event(ev("role_assigned", {"role": "wolf"})).lower()


@pytest.mark.parametrize(
    "type",
    ["pass", "vote_cast", "moderator_pick", "phase_change", "notes_turn_done"],
)
def test_engine_types_not_rendered(type):
    assert render_event(ev(type, {"reason": "SECRET"})) == ""


def test_engine_event_never_in_prompt():
    t = text(build(events=[ev("moderator_pick", {"reason": "SECRET"})]))
    assert "SECRET" not in t


# ---- end-to-end pipeline, leak canaries, seer anonymity ----


@pytest.fixture
def game():
    make_characters()
    return create_game(seed=3)


def canary(label):
    return f"CANARY_{label}_ZZ"


def plant(game):
    players = list(game.players.select_related("character"))
    wolves = [p for p in players if p.role == "wolf"]
    for p in players:
        append_note(p, canary(f"notes{p.id}"))
    for p in players:
        append_event(
            game,
            type="notes_turn_done",
            visibility=player_visibility(p.id),
            actor=p,
            payload={"phase": canary(f"private{p.id}")},
        )
    for i, w in enumerate(wolves):
        append_event(
            game,
            type="wolf_message",
            visibility=WOLF_CHAT,
            actor=w,
            payload={"message": canary(f"wolfchat{i}"), "kill_target_id": None},
        )
    append_event(
        game,
        type="moderator_pick",
        visibility=ENGINE,
        payload={"reason": canary("modpick"), "pick_id": None, "end": False},
    )
    speaker = next(p for p in players if p.role == "villager")
    append_event(
        game,
        type="vote_cast",
        visibility=ENGINE,
        actor=speaker,
        payload={"target_id": None, "note": canary("votecast")},
    )
    append_event(
        game,
        type="speech",
        visibility=PUBLIC,
        actor=speaker,
        payload={"message": canary("public")},
    )
    return players, wolves


def t_for(kind):
    return Turn(
        phase="discussion",
        day=1,
        kind=kind,
        allowed_tools=[],
    )


def test_leak_canaries(game):
    players, wolves = plant(game)
    seer = next(p for p in players if p.role == "seer")
    wolf_ids = {w.id for w in wolves}
    for p in players:
        for kind in KINDS:
            prompt = text(build_prompt_for(p, t_for(kind)))
            for q in players:
                if q.id != p.id:
                    assert canary(f"notes{q.id}") not in prompt
                    assert canary(f"private{q.id}") not in prompt
                assert canary("modpick") not in prompt
                assert canary("votecast") not in prompt
            assert canary("public") in prompt
            assert canary(f"notes{p.id}") in prompt
            sees_wolf_chat = p.id in wolf_ids or p.id == seer.id
            for i in range(2):
                assert (canary(f"wolfchat{i}") in prompt) is sees_wolf_chat


def test_non_wolves_never_see_wolf_names_in_role_section(game):
    players, wolves = plant(game)
    for p in players:
        if p.role == "wolf":
            continue
        prompt = text(build_prompt_for(p, t_for("discussion")))
        section = prompt.split("## Who you are")[0]
        for w in wolves:
            assert w.name not in section
        assert "teammate" not in section.lower()


def test_seer_wolf_chat_anonymised(game):
    players, wolves = plant(game)
    seer = next(p for p in players if p.role == "seer")
    prompt = text(build_prompt_for(seer, t_for("seer_notes")))
    log = prompt.split("## What you can see (today)")[1].split("## Your private")[0]
    assert "Wolf A:" in log
    assert "Wolf B:" in log
    for w in wolves:
        assert w.name not in log
        assert f'"actor": {w.id}' not in prompt
    assert "actor" not in log
    assert "player_id" not in prompt


def test_wolf_prompt_via_pipeline_has_teammate(game):
    _players, wolves = plant(game)
    w1, w2 = wolves
    prompt = text(build_prompt_for(w1, t_for("wolf_chat")))
    assert w2.name in prompt
    assert w1.wolf_label in prompt
    assert w2.wolf_label in prompt


def test_player_view_from_player(game):
    w = game.players.filter(role="wolf").first()
    v = player_view(w)
    assert v.name == w.name
    assert v.role == "wolf"
    assert v.wolf_label == w.wolf_label
    assert v.teammate_name is not None
    assert v.win_condition
    s = game.players.get(role="seer")
    sv = player_view(s)
    assert sv.wolf_label is None
    assert sv.teammate_name is None


def test_dead_roster_flag_via_pipeline(game):
    v = game.players.filter(role="villager")[0]
    dead = game.players.filter(role="villager")[1]
    Player.objects.filter(pk=dead.pk).update(alive=False)
    prompt = text(build_prompt_for(v, t_for("discussion")))
    assert f"{dead.name} (dead, was a villager)" in prompt
    game.config = {**game.config, "reveal_role_on_death": False}
    game.save()
    v.refresh_from_db()
    prompt = text(build_prompt_for(v, t_for("discussion")))
    assert f"{dead.name} (dead)" in prompt
