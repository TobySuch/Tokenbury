import pytest

from werewolf.events import append_event
from werewolf.models import PUBLIC, PlayerNotes
from werewolf.notes import (
    NotesError,
    append_note,
    current_notes,
    notes_as_of,
    replace_notes,
)
from werewolf.tests.factories import create_classic_game, make_characters

pytestmark = pytest.mark.django_db


@pytest.fixture
def game():
    make_characters()
    return create_classic_game(seed=3)


@pytest.fixture
def player(game):
    return game.players.first()


def test_empty_by_default(player):
    assert current_notes(player) == ""


def test_append_joins_with_newline_and_versions(player):
    n1 = append_note(player, "one")
    n2 = append_note(player, "two")
    assert (n1.version, n2.version) == (1, 2)
    assert current_notes(player) == "one\ntwo"
    assert PlayerNotes.objects.filter(player=player).count() == 2


def test_replace(player):
    append_note(player, "one")
    n = replace_notes(player, "fresh")
    assert n.version == 2
    assert current_notes(player) == "fresh"


def test_empty_rejected(player):
    for fn in (append_note, replace_notes):
        with pytest.raises(NotesError):
            fn(player, "   ")


def test_cap_reports_remaining(player):
    append_note(player, "x" * 2990)
    with pytest.raises(NotesError, match=r"9 characters remaining"):
        append_note(player, "y" * 10)
    with pytest.raises(NotesError, match="3000 characters remaining"):
        replace_notes(player, "z" * 3001)
    assert len(current_notes(player)) == 2990


def test_cap_from_config():
    make_characters()
    g = create_classic_game(seed=5, config={"notes_max_chars": 10})
    p = g.players.first()
    with pytest.raises(NotesError):
        append_note(p, "x" * 11)


def test_at_seq_and_notes_as_of(game, player):
    start = game.events.count()
    n1 = append_note(player, "a")
    assert n1.at_seq == start
    append_event(
        game, type="speech", visibility=PUBLIC, actor=player, payload={"message": "m"}
    )
    n2 = append_note(player, "b")
    assert n2.at_seq == start + 1
    assert notes_as_of(player, start - 1) is None
    assert notes_as_of(player, start).version == 1
    assert notes_as_of(player, start + 5).version == 2


def test_at_seq_zero_without_events():
    from werewolf.models import Player
    from werewolf.tests.factories import make_game

    make_characters()
    g = make_game()
    from werewolf.models import Character

    p = Player.objects.create(
        game=g, character=Character.objects.first(), seat=0, role="villager"
    )
    assert append_note(p, "x").at_seq == 0


def test_notes_isolated_between_players(game):
    a, b = game.players.all()[:2]
    append_note(a, "secret")
    assert current_notes(b) == ""
