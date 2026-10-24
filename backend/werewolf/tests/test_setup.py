from collections import Counter

import pytest

from werewolf.config import build_config, role_counts
from werewolf.models import Game, GameEvent, Player
from werewolf.setup import WIN_CONDITIONS, create_game
from werewolf.tests.factories import make_characters


@pytest.fixture
def cast(db):
    return make_characters(9)


def roles_by_seat(game):
    return [(p.seat, p.character.name, p.role) for p in game.players.order_by("seat")]


def test_requires_enough_characters(db):
    make_characters(6)
    with pytest.raises(ValueError, match="seed_werewolf_characters"):
        create_game(seed=1)
    with pytest.raises(ValueError, match="seed_werewolf_characters"):
        create_game(seed=1, config={"player_count": 9})


def test_initial_state(cast):
    game = create_game(seed=5)
    assert game.seed == 5
    assert game.status == Game.Status.ACTIVE
    assert game.phase == Game.Phase.NIGHT_WOLF_CHAT
    assert game.day_number == 1
    assert game.config["max_days"] == 8
    assert [p.seat for p in game.players.order_by("seat")] == list(range(7))


def test_random_seed_when_none(cast):
    assert isinstance(create_game().seed, int)


def test_role_distribution(cast):
    game = create_game(seed=3)
    counts = Counter(p.role for p in game.players.all())
    assert counts == {"wolf": 2, "seer": 1, "doctor": 1, "villager": 3}


@pytest.mark.parametrize("players", range(5, 13))
def test_role_distribution_follows_role_counts(db, players):
    make_characters(12)
    cfg = {"player_count": players}
    game = create_game(seed=3, config=cfg)
    counts = Counter(p.role for p in game.players.all())
    expected = role_counts(build_config(cfg))
    assert counts == {r: n for r, n in expected.items() if n}
    assert game.players.count() == players


def test_wolf_labels_for_three_wolves_in_seat_order(db):
    make_characters(12)
    game = create_game(seed=2, config={"player_count": 12})
    wolves = game.players.filter(role="wolf").order_by("seat")
    assert [p.wolf_label for p in wolves] == ["Wolf A", "Wolf B", "Wolf C"]


def test_lovers_never_both_wolves_and_links_symmetric(db):
    make_characters(12)
    for seed in range(60):
        game = create_game(seed=seed, config={"player_count": 5 + seed % 8})
        linked = list(game.players.filter(lover__isnull=False))
        assert len(linked) == 2
        a, b = linked
        assert a.lover_id == b.pk and b.lover_id == a.pk
        assert not (a.role == "wolf" and b.role == "wolf")


def test_lovers_off_means_no_links(cast):
    game = create_game(seed=4, config={"lovers": False})
    assert not game.players.filter(lover__isnull=False).exists()
    for e in GameEvent.objects.filter(game=game, type="role_assigned"):
        assert "lover_name" not in e.payload
        assert "lovers_note" not in e.payload


def test_lover_pairing_deterministic(cast):
    def pair(game):
        return {p.seat for p in game.players.filter(lover__isnull=False)}

    assert pair(create_game(seed=21)) == pair(create_game(seed=21))


def test_deterministic_for_seed(cast):
    a = roles_by_seat(create_game(seed=99))
    b = roles_by_seat(create_game(seed=99))
    assert a == b


def test_different_seeds_vary(cast):
    results = {tuple(roles_by_seat(create_game(seed=s))) for s in range(10)}
    assert len(results) > 1


def test_wolf_labels_only_on_wolves(cast):
    game = create_game(seed=7)
    wolves = game.players.filter(role="wolf")
    assert sorted(p.wolf_label for p in wolves) == ["Wolf A", "Wolf B"]
    assert [p.wolf_label for p in wolves.order_by("seat")] == ["Wolf A", "Wolf B"]
    assert all(not p.wolf_label for p in game.players.exclude(role="wolf"))


def test_role_assigned_events(cast):
    game = create_game(seed=7)
    events = GameEvent.objects.filter(game=game, type="role_assigned")
    assert events.count() == 7
    for p in game.players.all():
        (e,) = [e for e in events if e.actor_id == p.id]
        assert e.visibility == f"player:{p.id}"
        assert e.payload["role"] == p.role
        assert e.payload["win_condition"]
        expected = {"role", "win_condition"}
        if p.role == "wolf":
            mates = game.players.filter(role="wolf").exclude(pk=p.pk)
            assert e.payload["wolf_label"] == p.wolf_label
            assert e.payload["teammates"] == [
                {"name": m.character.name, "label": m.wolf_label} for m in mates
            ]
            expected |= {"wolf_label", "teammates"}
        if p.role == "doctor":
            assert e.payload["win_condition"] == WIN_CONDITIONS["villager"]
        if p.lover_id:
            partner = game.players.get(pk=p.lover_id)
            assert e.payload["lover_name"] == partner.character.name
            assert "last two" in e.payload["lovers_note"]
            expected |= {"lover_name", "lovers_note"}
        assert set(e.payload) == expected


def test_lovers_payload_never_names_partner_role(cast):
    for seed in range(20):
        game = create_game(seed=seed)
        for p in game.players.filter(lover__isnull=False):
            e = GameEvent.objects.get(game=game, type="role_assigned", actor=p)
            assert set(e.payload) >= {"lover_name", "lovers_note"}
            assert "partner_role" not in e.payload
            assert "lover_role" not in e.payload
            assert set(e.payload) <= {
                "role",
                "win_condition",
                "wolf_label",
                "teammates",
                "lover_name",
                "lovers_note",
            }


def test_config_overrides(cast):
    game = create_game(seed=1, config={"max_days": "3"})
    assert game.config["max_days"] == 3
    with pytest.raises(ValueError):
        create_game(seed=1, config={"nope": 1})


def test_create_game_picks_subset(cast):
    game = create_game(seed=1)
    assert Player.objects.filter(game=game).count() == 7


@pytest.mark.django_db
def test_new_games_start_unpublished_unless_asked():
    make_characters()
    assert create_game(seed=1).published is False
    assert create_game(seed=2, published=True).published is True
