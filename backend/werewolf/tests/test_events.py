import pytest

from werewolf.events import append_event
from werewolf.models import Game, GameEvent
from werewolf.tests.factories import make_game


@pytest.mark.django_db
def test_seq_monotonic_from_one():
    game = make_game()
    seqs = [
        append_event(game, type=GameEvent.Type.PHASE_CHANGE, visibility="engine").seq
        for _ in range(3)
    ]
    assert seqs == [1, 2, 3]


@pytest.mark.django_db
def test_seq_independent_across_games():
    g1, g2 = make_game(), make_game()
    append_event(g1, type="phase_change", visibility="engine")
    append_event(g1, type="phase_change", visibility="engine")
    assert append_event(g2, type="phase_change", visibility="engine").seq == 1


@pytest.mark.django_db
def test_defaults_day_and_phase_from_game():
    game = make_game(day_number=2, phase=Game.Phase.DISCUSSION)
    e = append_event(game, type="speech", visibility="public")
    assert (e.day, e.phase) == (2, "discussion")
    assert e.payload == {}
    e2 = append_event(game, type="speech", visibility="public", day=1, phase="vote")
    assert (e2.day, e2.phase) == (1, "vote")


@pytest.mark.django_db
def test_stale_game_instance_still_gets_next_seq():
    game = make_game()
    stale = Game.objects.get(pk=game.pk)
    append_event(game, type="speech", visibility="public")
    assert append_event(stale, type="speech", visibility="public").seq == 2
