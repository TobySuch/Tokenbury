from collections import Counter

import pytest

from werewolf.models import Game, GameEvent, Player
from werewolf.setup import create_game
from werewolf.tests.factories import make_characters


@pytest.fixture
def cast(db):
    return make_characters(9)


def roles_by_seat(game):
    return [(p.seat, p.character.name, p.role) for p in game.players.order_by("seat")]


def test_requires_seven_characters(db):
    make_characters(6)
    with pytest.raises(ValueError):
        create_game(seed=1)


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
    assert counts == {"wolf": 2, "seer": 1, "villager": 4}


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
        if p.role == "wolf":
            mate = game.players.filter(role="wolf").exclude(pk=p.pk).get()
            assert e.payload["wolf_label"] == p.wolf_label
            assert e.payload["teammate_name"] == mate.character.name
            assert e.payload["teammate_label"] == mate.wolf_label
        else:
            assert set(e.payload) == {"role", "win_condition"}


def test_config_overrides(cast):
    game = create_game(seed=1, config={"max_days": "3"})
    assert game.config["max_days"] == 3
    with pytest.raises(ValueError):
        create_game(seed=1, config={"nope": 1})


def test_create_game_picks_subset(cast):
    game = create_game(seed=1)
    assert Player.objects.filter(game=game).count() == 7
