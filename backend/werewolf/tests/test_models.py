import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from werewolf.models import Character, Game, Player, player_visibility
from werewolf.tests.factories import make_characters, make_game


@pytest.mark.django_db
def test_character_talkativeness_validated():
    with pytest.raises(ValidationError):
        Character(name="X", talkativeness=6).full_clean(exclude=["avatar"])
    with pytest.raises(ValidationError):
        Character(name="X", talkativeness=0).full_clean(exclude=["avatar"])
    Character(name="X", talkativeness=3).full_clean(exclude=["avatar"])


@pytest.mark.django_db
def test_game_defaults():
    game = make_game()
    assert game.status == Game.Status.ACTIVE
    assert game.phase == Game.Phase.SETUP
    assert game.day_number == 0
    assert game.winner is None


@pytest.mark.django_db
def test_player_unique_seat_and_character():
    game = make_game()
    a, b = make_characters(2)
    Player.objects.create(game=game, character=a, seat=0, role=Player.Role.WOLF)
    with pytest.raises(IntegrityError):
        Player.objects.create(game=game, character=b, seat=0, role=Player.Role.WOLF)


@pytest.mark.django_db
def test_player_unique_character_per_game():
    game = make_game()
    (a,) = make_characters(1)
    Player.objects.create(game=game, character=a, seat=0, role=Player.Role.WOLF)
    with pytest.raises(IntegrityError):
        Player.objects.create(game=game, character=a, seat=1, role=Player.Role.WOLF)


def test_player_visibility_helper():
    assert player_visibility(5) == "player:5"
