import itertools

import pytest

from werewolf.beats import build_beats
from werewolf.engine import ScriptedProvider, run_day
from werewolf.events import append_event
from werewolf.models import ENGINE, PUBLIC, WOLF_CHAT, Game, GameEvent
from werewolf.setup import create_game
from werewolf.tests.factories import create_classic_game, make_characters

pytestmark = pytest.mark.django_db

KEYS = {
    "index", "seq", "day", "phase", "kind", "palette", "banner", "actor_id",
    "text", "kill_target_id", "victim_id", "role", "votes", "tally", "winner",
    "alive_ids", "target_id",
}  # fmt: skip


def new_game(seed=3):
    make_characters(7)
    return create_classic_game(seed=seed)


def ev(game, type, vis, day, phase, actor=None, **payload):
    return append_event(
        game, type=type, visibility=vis, day=day, phase=phase, actor=actor,
        payload=payload,
    )  # fmt: skip


def test_hand_built_log_exact_beats():
    game = new_game()
    ids = list(game.players.order_by("seat").values_list("id", flat=True))
    wolf = game.players.filter(role="wolf").first()
    victim = game.players.exclude(role="wolf").first()
    other = game.players.exclude(role="wolf").exclude(pk=victim.pk).first()
    last_role = GameEvent.objects.filter(type="role_assigned").order_by("-seq")[0].seq
    N, D = "night_wolf_chat", "discussion"
    ev(
        game,
        "wolf_message",
        WOLF_CHAT,
        1,
        N,
        wolf,
        message="hi",
        kill_target_id=victim.id,
    )
    ev(game, "wolf_target", WOLF_CHAT, 1, N, target_id=victim.id, source="agreed")
    ev(game, "phase_change", ENGINE, 1, N, **{"from": N, "to": "night_seer"})
    ev(
        game,
        "phase_change",
        ENGINE,
        1,
        "night_seer",
        **{"from": "night_seer", "to": "morning"},
    )
    ev(
        game,
        "death",
        PUBLIC,
        1,
        "morning",
        player_id=victim.id,
        cause="night_kill",
        role=None,
    )
    ev(game, "phase_change", ENGINE, 1, "morning", **{"from": "morning", "to": D})
    ev(game, "moderator_pick", ENGINE, 1, D, pick_id=other.id, end=False)
    ev(game, "speech", PUBLIC, 1, D, other, message="I am innocent")
    ev(
        game,
        "vote_result",
        PUBLIC,
        1,
        "vote",
        votes=[],
        tally={"none": 6},
        eliminated_id=None,
    )
    ev(game, "phase_change", ENGINE, 1, "day_notes", **{"from": "day_notes", "to": N})
    ev(
        game,
        "death",
        PUBLIC,
        2,
        "elimination",
        player_id=wolf.id,
        cause="vote",
        role=None,
    )
    ev(game, "game_over", PUBLIC, 2, "elimination", winner="town")  # fmt: skip

    beats = build_beats(game)
    assert all(set(b) == KEYS for b in beats)
    got = [(b["kind"], b["banner"], b["palette"], b["day"], b["phase"]) for b in beats]
    assert got == [
        ("phase_change", "Night 1", "night", 1, N),
        ("wolf_message", "Night 1", "night", 1, N),
        ("phase_change", "Night 1: The seer listens", "night", 1, "night_seer"),
        ("phase_change", "Day 1: Morning", "day", 1, "morning"),
        ("morning", "Day 1: Morning", "day", 1, "morning"),
        ("phase_change", "Day 1: Discussion", "day", 1, D),
        ("speech", "Day 1: Discussion", "day", 1, D),
        ("vote_reveal", "Day 1: Discussion", "day", 1, D),
        ("phase_change", "Night 2", "night", 2, N),
        ("elimination", "Night 2", "night", 2, N),
        ("game_over", "Night 2", "night", 2, N),
    ]
    assert [b["index"] for b in beats] == list(range(len(beats)))
    assert beats[0]["seq"] == last_role
    assert beats[0]["alive_ids"] == ids
    wm = beats[1]
    assert (wm["actor_id"], wm["text"], wm["kill_target_id"]) == (
        wolf.id,
        "hi",
        victim.id,
    )
    m = beats[4]
    assert m["victim_id"] == victim.id and m["role"] == victim.role
    assert victim.id not in m["alive_ids"] and victim.id in beats[3]["alive_ids"]
    assert beats[6]["actor_id"] == other.id and beats[6]["text"] == "I am innocent"
    v = beats[7]
    assert v["text"] == "No one was eliminated." and v["tally"] == {"none": 6}
    assert v["votes"] == []
    e = beats[9]
    assert e["role"] == "wolf" and wolf.id not in e["alive_ids"]
    assert beats[10]["winner"] == "town"
    assert len(beats[10]["alive_ids"]) == 5


def test_vote_reveal_with_votes_and_elimination_text():
    game = new_game()
    a, b = list(game.players.all()[:2])
    ev(game, "vote_result", PUBLIC, 1, "vote",
       votes=[{"voter_id": a.id, "target_id": b.id}],
       tally={str(b.id): 1}, eliminated_id=b.id)  # fmt: skip
    beat = build_beats(game)[1]
    assert beat["votes"] == [{"voter_id": a.id, "target_id": b.id}]
    assert beat["tally"] == {str(b.id): 1}
    assert b.name in beat["text"]


def test_scripted_full_game():
    game = new_game(seed=11)
    provider = ScriptedProvider(game)
    for _ in range(20):
        run_day(game, provider)
        game.refresh_from_db()
        if game.status != Game.Status.ACTIVE:
            break
    assert game.status == Game.Status.FINISHED
    beats = build_beats(game)
    assert beats[0]["kind"] == "phase_change" and beats[-1]["kind"] == "game_over"
    assert [b["index"] for b in beats] == list(range(len(beats)))
    seqs = [b["seq"] for b in beats]
    assert seqs == sorted(seqs) and len(set(seqs[1:])) == len(seqs) - 1
    for prev, cur in itertools.pairwise(beats):
        shrunk = set(prev["alive_ids"]) - set(cur["alive_ids"])
        if cur["kind"] in ("morning", "elimination"):
            assert shrunk == {cur["victim_id"]}
        else:
            assert not shrunk
    for etype, kind in (("speech", "speech"), ("wolf_message", "wolf_message")):
        want = set(
            GameEvent.objects.filter(game=game, type=etype).values_list(
                "seq", flat=True
            )
        )
        assert want == {b["seq"] for b in beats if b["kind"] == kind}
    assert beats[-1]["winner"] == game.winner


def test_new_kinds_hand_built():
    game = new_game()
    doctor, other, wolf = list(game.players.order_by("seat")[:3])
    ND, NL = "night_doctor", "night_lovers"
    ev(
        game,
        "phase_change",
        ENGINE,
        1,
        "night_wolf_chat",
        **{"from": "night_wolf_chat", "to": ND},
    )
    ev(game, "protect", f"player:{doctor.id}", 1, ND, doctor, target_id=other.id)
    ev(game, "save_result", f"player:{doctor.id}", 1, ND, saved=True)
    ev(game, "phase_change", ENGINE, 1, ND, **{"from": ND, "to": NL})
    ev(game, "lover_message", "lovers", 1, NL, doctor, message="darling")
    ev(game, "phase_change", ENGINE, 1, NL, **{"from": NL, "to": "morning"})
    ev(game, "peaceful_night", PUBLIC, 1, "morning")
    ev(
        game,
        "death",
        PUBLIC,
        2,
        "morning",
        player_id=other.id,
        cause="night_kill",
        role=None,
    )
    ev(
        game,
        "death",
        PUBLIC,
        2,
        "morning",
        player_id=wolf.id,
        cause="heartbreak",
        role=None,
    )
    ev(
        game,
        "death",
        PUBLIC,
        3,
        "elimination",
        player_id=doctor.id,
        cause="vote",
        role=None,
    )
    ev(game, "death", PUBLIC, 3, "elimination", player_id=game.players.order_by("seat")[3].id, cause="heartbreak", role=None)  # fmt: skip

    beats = build_beats(game)
    assert all(set(b) == KEYS for b in beats)
    assert [b["kind"] for b in beats] == [
        "phase_change", "phase_change", "protect", "phase_change", "lover_message",
        "phase_change", "peaceful_night", "morning", "heartbreak", "elimination",
        "heartbreak",
    ]  # fmt: skip
    assert beats[1]["banner"] == "Night 1: The doctor's rounds"
    assert beats[3]["banner"] == "Night 1: The lovers whisper"
    assert beats[3]["palette"] == "night"
    pr = beats[2]
    assert (pr["palette"], pr["actor_id"], pr["target_id"]) == (
        "night",
        doctor.id,
        other.id,
    )
    assert pr["text"] == f"The doctor protects {other.name}."
    lm = beats[4]
    assert (lm["palette"], lm["actor_id"], lm["text"]) == (
        "night",
        doctor.id,
        "darling",
    )
    pn = beats[6]
    assert (pn["palette"], pn["text"]) == ("day", "Nobody died last night.")
    hb = beats[8]
    assert (
        hb["palette"] == "day"
        and hb["victim_id"] == wolf.id
        and hb["role"] == wolf.role
    )
    assert hb["text"] == f"{wolf.name} died of a broken heart."
    assert other.id not in hb["alive_ids"] and wolf.id not in hb["alive_ids"]
    assert beats[7]["target_id"] is None
    assert doctor.id not in beats[10]["alive_ids"]
    assert len(beats[10]["alive_ids"]) == len(beats[9]["alive_ids"]) - 1


def test_scripted_full_default_game():
    make_characters(9)
    game = create_game(seed=5, config={"player_count": 9})
    provider = ScriptedProvider(game)
    for _ in range(20):
        run_day(game, provider)
        game.refresh_from_db()
        if game.status != Game.Status.ACTIVE:
            break
    assert game.status == Game.Status.FINISHED
    beats = build_beats(game)
    assert all(set(b) == KEYS for b in beats)
    assert [b["index"] for b in beats] == list(range(len(beats)))
    assert not [b for b in beats if b["kind"] == "save_result"]
    for etype in ("lover_message", "protect", "peaceful_night"):
        want = set(
            GameEvent.objects.filter(game=game, type=etype).values_list(
                "seq", flat=True
            )
        )
        assert want == {b["seq"] for b in beats if b["kind"] == etype}
    hb = set(
        GameEvent.objects.filter(
            game=game, type="death", payload__cause="heartbreak"
        ).values_list("seq", flat=True)
    )
    assert hb == {b["seq"] for b in beats if b["kind"] == "heartbreak"}
    assert all(b["target_id"] for b in beats if b["kind"] == "protect")
    for prev, cur in itertools.pairwise(beats):
        shrunk = set(prev["alive_ids"]) - set(cur["alive_ids"])
        if cur["kind"] in ("morning", "elimination", "heartbreak"):
            assert shrunk == {cur["victim_id"]}
        else:
            assert not shrunk


def test_skipping_non_beat_events_changes_nothing(
    monkeypatch, django_assert_num_queries
):
    make_characters(9)
    game = create_game(seed=5, config={"player_count": 9})
    provider = ScriptedProvider(game)
    while game.status == Game.Status.ACTIVE:
        run_day(game, provider)
        game.refresh_from_db()
    with django_assert_num_queries(2):
        filtered = build_beats(game)
    monkeypatch.setattr("werewolf.beats.BEAT_EVENT_TYPES", set(GameEvent.Type.values))
    assert filtered == build_beats(game)


def test_unknown_death_cause_is_a_generic_day_beat():
    game = new_game()
    victim = game.players.exclude(role="wolf").first()
    ev(game, "death", PUBLIC, 1, "morning", player_id=victim.id, cause="plague")
    beat = next(b for b in build_beats(game) if b["victim_id"] == victim.id)
    assert beat["kind"] == "morning"
    assert beat["text"] == f"{victim.name} died."


def test_day_end_banner_then_next_night_counts_the_new_day():
    game = new_game()
    N = "night_wolf_chat"
    ev(game, "phase_change", ENGINE, 1, "day_notes", **{"from": "day_notes", "to": "day_end"})  # fmt: skip
    ev(game, "phase_change", ENGINE, 1, "day_end", **{"from": "day_end", "to": N})
    got = [(b["banner"], b["palette"], b["day"]) for b in build_beats(game)][-2:]
    assert got == [("Day 1: End of day", "day", 1), ("Night 2", "night", 2)]
