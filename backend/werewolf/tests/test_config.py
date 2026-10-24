import pytest

from werewolf.config import DEFAULT_CONFIG, build_config, game_config, role_counts
from werewolf.tests.factories import make_game


def test_defaults():
    cfg = build_config({})
    assert cfg == DEFAULT_CONFIG
    assert cfg["wolf_chat_max_messages"] == 6
    assert cfg["reveal_role_on_death"] is True
    assert cfg["call_budget"] == 400


def test_overrides_merge_without_mutating_defaults():
    cfg = build_config({"max_days": 3})
    assert cfg["max_days"] == 3
    assert DEFAULT_CONFIG["max_days"] == 8


def test_unknown_key_rejected():
    with pytest.raises(ValueError, match="bogus"):
        build_config({"bogus": 1})


def test_string_coercion():
    cfg = build_config({
        "max_days": "3",
        "votes_public": "false",
        "reveal_role_on_death": "1",
    })
    assert cfg["max_days"] == 3
    assert cfg["votes_public"] is False
    assert cfg["reveal_role_on_death"] is True


def test_bad_values_rejected():
    with pytest.raises(ValueError):
        build_config({"max_days": "abc"})
    with pytest.raises(ValueError):
        build_config({"votes_public": "maybe"})


@pytest.mark.django_db
def test_game_config_merges_stored_overrides():
    game = make_game(config={"max_days": 2})
    cfg = game_config(game)
    assert cfg["max_days"] == 2
    assert cfg["speech_max_chars"] == 400


@pytest.mark.parametrize(
    ("players", "mix"),
    [
        (5, (1, 1, 0, 3)),
        (6, (2, 1, 1, 2)),
        (7, (2, 1, 1, 3)),
        (8, (2, 1, 1, 4)),
        (9, (3, 1, 1, 4)),
        (10, (3, 1, 1, 5)),
        (11, (3, 1, 1, 6)),
        (12, (3, 1, 1, 7)),
    ],
)
def test_role_counts_auto_mix(players, mix):
    counts = role_counts(build_config({"player_count": players}))
    assert (
        counts["wolf"],
        counts["seer"],
        counts["doctor"],
        counts["villager"],
    ) == mix
    assert sum(counts.values()) == players


def test_new_config_defaults():
    cfg = build_config({})
    assert cfg["player_count"] == 7
    assert cfg["wolf_count"] is None
    assert cfg["seer_count"] is None
    assert cfg["doctor_count"] is None
    assert cfg["lovers"] is True
    assert cfg["lovers_chat_max_messages"] == 4


def test_role_count_overrides():
    cfg = build_config({"player_count": 9, "wolf_count": 2, "doctor_count": 0})
    assert role_counts(cfg) == {"wolf": 2, "seer": 1, "doctor": 0, "villager": 6}
    cfg = build_config({"seer_count": "0", "doctor_count": "1"})
    assert role_counts(cfg) == {"wolf": 2, "seer": 0, "doctor": 1, "villager": 4}


@pytest.mark.parametrize("raw", [None, "null", "none", "auto", ""])
def test_none_default_keys_accept_null(raw):
    assert build_config({"wolf_count": raw})["wolf_count"] is None


def test_none_default_keys_reject_junk():
    with pytest.raises(ValueError, match="wolf_count"):
        build_config({"wolf_count": "lots"})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"player_count": 4}, "player_count"),
        ({"player_count": 13}, "player_count"),
        ({"wolf_count": 0}, "at least 1 wolf"),
        ({"wolf_count": 4}, "fewer"),
        ({"player_count": 6, "wolf_count": 3}, "fewer"),
        ({"seer_count": 2}, "seer"),
        ({"doctor_count": 2}, "doctor"),
        ({"seer_count": -1}, "seer_count"),
    ],
)
def test_invalid_mixes_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        build_config(overrides)


@pytest.mark.django_db
def test_legacy_stored_config_gets_classic_rules():
    from werewolf.setup import create_game
    from werewolf.tests.factories import make_characters

    make_characters(7)
    game = create_game(seed=1, config={"doctor_count": 0, "lovers": False})
    game.config = {"max_days": 3}  # stored before player_count existed
    game.save()
    cfg = game_config(game)
    assert cfg["player_count"] == 7
    assert cfg["doctor_count"] == 0
    assert cfg["lovers"] is False
    assert cfg["max_days"] == 3
    assert role_counts(cfg) == {"wolf": 2, "seer": 1, "doctor": 0, "villager": 4}


@pytest.mark.django_db
def test_modern_stored_config_is_untouched():
    game = make_game(config=build_config({"player_count": 8}))
    cfg = game_config(game)
    assert cfg["doctor_count"] is None and cfg["lovers"] is True
