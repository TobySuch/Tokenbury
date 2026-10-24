import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from werewolf.events import append_event
from werewolf.models import ENGINE, PUBLIC, WOLF_CHAT, Player, player_visibility
from werewolf.notes import append_note
from werewolf.setup import create_game
from werewolf.tests.factories import make_characters
from werewolf.visibility import (
    VisibleEvent,
    build_roster,
    events_visible_to,
    own_role_info,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def game():
    make_characters()
    return create_game(seed=3)


def by_role(game, role):
    return list(game.players.filter(role=role))


def wolves(game):
    return by_role(game, "wolf")


def seer(game):
    return by_role(game, "seer")[0]


def villagers(game):
    return by_role(game, "villager")


def seq_types(events):
    return [e.type for e in events]


def test_visibility_matrix(game):
    w1, w2 = wolves(game)
    s = seer(game)
    v1, v2 = villagers(game)[:2]
    append_event(
        game, type="speech", visibility=PUBLIC, actor=v1, payload={"message": "hi"}
    )
    append_event(
        game,
        type="wolf_message",
        visibility=WOLF_CHAT,
        actor=w1,
        payload={"message": "w", "kill_target_id": None},
    )
    append_event(
        game, type="pass", visibility=ENGINE, actor=v1, payload={"phase": "discussion"}
    )
    append_event(
        game,
        type="notes_turn_done",
        visibility=player_visibility(v2.id),
        actor=v2,
        payload={"phase": "x"},
    )

    def types(p):
        return seq_types(events_visible_to(p))

    for p in (w1, w2, s):
        assert "wolf_message" in types(p)
    for p in villagers(game):
        assert "wolf_message" not in types(p)
    for p in game.players.all():
        t = types(p)
        assert "speech" in t
        assert "pass" not in t
        assert "role_assigned" in t
        assert ("notes_turn_done" in t) == (p.id == v2.id)


def test_ordered_by_seq_and_returns_visible_event(game):
    v = villagers(game)[0]
    append_event(
        game, type="speech", visibility=PUBLIC, actor=v, payload={"message": "a"}
    )
    events = events_visible_to(v)
    assert all(isinstance(e, VisibleEvent) for e in events)
    assert [e.seq for e in events] == sorted(e.seq for e in events)
    assert events[-1].speaker == v.name


def test_wolf_chat_anonymised_for_seer_and_wolves(game):
    w1, w2 = wolves(game)
    s = seer(game)
    victim = villagers(game)[0]
    append_event(
        game,
        type="wolf_message",
        visibility=WOLF_CHAT,
        actor=w1,
        payload={"message": "kill", "kill_target_id": victim.id},
    )
    append_event(
        game,
        type="wolf_target",
        visibility=WOLF_CHAT,
        payload={"target_id": victim.id, "source": "agreed"},
    )
    events = [e for e in events_visible_to(s) if e.type.startswith("wolf_")]
    assert events[0].speaker == w1.wolf_label
    assert events[0].payload["kill_target"] == victim.name
    assert events[1].speaker is None
    assert events[1].payload == {"target": victim.name, "source": "agreed"}
    text = repr([e for e in events_visible_to(s) if e.type.startswith("wolf_")])
    for w in (w1, w2):
        assert w.name not in text
        assert f"id': {w.id}" not in text
        assert "actor" not in text
    mine = [e for e in events_visible_to(w1) if e.type == "wolf_message"]
    assert mine[0].speaker == w1.wolf_label


def test_dead_player_cutoff(game):
    v1, v2 = villagers(game)[:2]
    append_event(
        game, type="speech", visibility=PUBLIC, actor=v2, payload={"message": "before"}
    )
    append_event(
        game,
        type="death",
        visibility=PUBLIC,
        payload={"player_id": v1.id, "cause": "night_kill", "role": "villager"},
    )
    append_event(
        game, type="speech", visibility=PUBLIC, actor=v2, payload={"message": "after"}
    )
    dead = events_visible_to(v1)
    assert dead[-1].type == "death"
    assert dead[-1].payload["player"] == v1.name
    assert "after" not in repr(dead)
    assert "after" in repr(events_visible_to(v2))


def test_day_filter(game):
    v = villagers(game)[0]
    append_event(
        game,
        type="speech",
        visibility=PUBLIC,
        day=1,
        actor=v,
        payload={"message": "d1"},
    )
    append_event(
        game,
        type="speech",
        visibility=PUBLIC,
        day=2,
        actor=v,
        payload={"message": "d2"},
    )
    assert [e.payload["message"] for e in events_visible_to(v, day=2)] == ["d2"]
    assert len(events_visible_to(v)) == 3


def test_payload_conversion(game):
    a, b, c = villagers(game)[:3]
    append_event(
        game,
        type="vote_result",
        visibility=PUBLIC,
        payload={
            "votes": [
                {"voter_id": a.id, "target_id": b.id},
                {"voter_id": b.id, "target_id": None},
            ],
            "tally": {str(b.id): 1, "none": 1},
            "eliminated_id": b.id,
        },
    )
    e = events_visible_to(c)[-1]
    assert e.payload == {
        "votes": [
            {"voter": a.name, "target": b.name},
            {"voter": b.name, "target": None},
        ],
        "tally": {b.name: 1, "none": 1},
        "eliminated": b.name,
    }
    assert e.speaker is None


def test_death_role_dropped_when_flag_off():
    make_characters()
    g = create_game(seed=4, config={"reveal_role_on_death": False})
    v = g.players.filter(role="villager").first()
    append_event(
        g,
        type="death",
        visibility=PUBLIC,
        payload={"player_id": v.id, "cause": "vote", "role": "villager"},
    )
    e = events_visible_to(g.players.exclude(pk=v.pk).first())[-1]
    assert "role" not in e.payload
    assert e.payload["player"] == v.name


def test_death_role_kept_when_flag_on(game):
    v = villagers(game)[0]
    append_event(
        game,
        type="death",
        visibility=PUBLIC,
        payload={"player_id": v.id, "cause": "vote", "role": "villager"},
    )
    e = events_visible_to(seer(game))[-1]
    assert e.payload["role"] == "villager"


def test_query_count(game):
    p = seer(game)
    with CaptureQueriesContext(connection) as ctx:
        events_visible_to(p)
    assert len(ctx) <= 2


def test_roster_reveals(game):
    me, dead, alive = villagers(game)[:3]
    Player.objects.filter(pk=dead.pk).update(alive=False)
    me.refresh_from_db()
    roster = build_roster(me)
    names = [r.name for r in roster]
    assert me.name not in names
    assert len(roster) == 6
    assert names == [p.name for p in game.players.order_by("seat") if p.pk != me.pk]
    by_name = {r.name: r for r in roster}
    assert by_name[dead.name].alive is False
    assert by_name[dead.name].role == "villager"
    assert by_name[alive.name].alive and by_name[alive.name].role is None


def test_roster_hides_role_when_flag_off():
    make_characters()
    g = create_game(seed=4, config={"reveal_role_on_death": False})
    a, b = g.players.all()[:2]
    Player.objects.filter(pk=b.pk).update(alive=False)
    entry = next(r for r in build_roster(a) if r.name == b.name)
    assert entry.role is None and entry.alive is False


def test_own_role_info(game):
    w1, w2 = wolves(game)
    info = own_role_info(w1)
    assert info["role"] == "wolf"
    assert info["wolf_label"] == w1.wolf_label
    assert info["teammate_name"] == w2.name
    assert own_role_info(seer(game))["role"] == "seer"


def test_leak_canary(game):
    players = list(game.players.all())
    canary = {}
    for p in players:
        key = f"CANARY_NOTES_{p.id}"
        append_note(p, key)
        canary[p.id] = key
    own_role = {}
    for ev in game.events.filter(type="role_assigned"):
        ev.payload["win_condition"] = f"CANARY_ROLE_{ev.actor_id}"
        ev.save()
        own_role[ev.actor_id] = f"CANARY_ROLE_{ev.actor_id}"
    w1 = wolves(game)[0]
    append_event(
        game,
        type="wolf_message",
        visibility=WOLF_CHAT,
        actor=w1,
        payload={"message": "CANARY_WOLF", "kill_target_id": None},
    )
    append_event(
        game,
        type="pass",
        visibility=ENGINE,
        actor=w1,
        payload={"phase": "CANARY_ENGINE"},
    )
    append_event(
        game,
        type="speech",
        visibility=PUBLIC,
        actor=w1,
        payload={"message": "CANARY_PUBLIC"},
    )

    from werewolf.notes import current_notes

    for p in players:
        text = repr(events_visible_to(p)) + current_notes(p)
        assert "CANARY_ENGINE" not in text
        assert "CANARY_PUBLIC" in text
        assert ("CANARY_WOLF" in text) == (p.role in ("wolf", "seer"))
        for pid, key in canary.items():
            assert (key in text) == (pid == p.id)
        for pid, key in own_role.items():
            assert (key in text) == (pid == p.id)


def test_dead_player_cutoff_holds_when_day_filter_excludes_death(game):
    v1, v2 = villagers(game)[:2]
    append_event(
        game,
        type="death",
        visibility=PUBLIC,
        day=1,
        payload={"player_id": v1.id, "cause": "night_kill", "role": "villager"},
    )
    append_event(
        game,
        type="speech",
        visibility=PUBLIC,
        day=2,
        actor=v2,
        payload={"message": "later"},
    )
    Player.objects.filter(pk=v1.pk).update(alive=False)
    v1.refresh_from_db()
    assert events_visible_to(v1, day=2) == []
    assert len(events_visible_to(v2, day=2)) == 1
