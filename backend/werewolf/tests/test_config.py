import pytest

from werewolf.config import DEFAULT_CONFIG, build_config, game_config
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
