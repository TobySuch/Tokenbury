import pytest
from django.core.management import CommandError, call_command

from werewolf.models import Character, Game
from werewolf.tests.factories import make_characters


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def test_seed_creates_seven_idempotently(db):
    call_command("seed_werewolf_characters")
    assert Character.objects.count() == 7
    call_command("seed_werewolf_characters")
    assert Character.objects.count() == 7
    talk = {c.talkativeness for c in Character.objects.all()}
    assert len(talk) >= 4 and all(1 <= t <= 5 for t in talk)
    assert all(c.avatar for c in Character.objects.all())


def test_create_game_command(db):
    make_characters(7)
    call_command("create_werewolf_game", "--seed", "11", "--config", "max_days=3")
    game = Game.objects.get()
    assert game.seed == 11
    assert game.config["max_days"] == 3
    assert game.players.count() == 7


def test_create_game_command_bad_config(db):
    make_characters(7)
    with pytest.raises(CommandError):
        call_command("create_werewolf_game", "--config", "bogus=1")
    with pytest.raises(CommandError):
        call_command("create_werewolf_game", "--config", "noequals")


def test_create_game_command_too_few_characters(db):
    with pytest.raises(CommandError):
        call_command("create_werewolf_game")
