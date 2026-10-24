import pytest

from werewolf import engine
from werewolf.engine import ScriptedProvider, run_day
from werewolf.models import AgentCall
from werewolf.tests.factories import create_classic_game, make_characters
from werewolf.tests.helpers import events_of

pytestmark = pytest.mark.django_db


class CrashError(Exception):
    pass


def comparable(game):
    """Everything that must match between a crashed+resumed and a clean run."""
    return [
        (
            e.day,
            e.phase,
            e.type,
            e.actor.seat if e.actor else None,
            e.payload.get("message"),
        )
        for e in events_of(game)
    ]


def clean_run(seed):
    game = create_classic_game(seed=seed)
    phases = []
    real = engine.run_turn

    def spy(game_, player, agent, turn, ctx, messages):
        phases.append(turn.phase)
        return real(game_, player, agent, turn, ctx, messages)

    engine.run_turn = spy
    try:
        run_day(game, ScriptedProvider(game))
    finally:
        engine.run_turn = real
    game.refresh_from_db()
    return game, phases


def crash_then_resume(seed, crash_at, monkeypatch):
    game = create_classic_game(seed=seed)
    real = engine.run_turn
    calls = {"n": 0}

    def crashing(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == crash_at:
            raise CrashError
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "run_turn", crashing)
    with pytest.raises(CrashError):
        run_day(game, ScriptedProvider(game))
    monkeypatch.setattr(engine, "run_turn", real)
    game.refresh_from_db()
    run_day(game, ScriptedProvider(game))
    game.refresh_from_db()
    return game


def assert_contiguous(game):
    seqs = [e.seq for e in events_of(game)]
    assert seqs == list(range(1, len(seqs) + 1))


def test_crash_at_every_turn_resumes_without_duplicates(monkeypatch):
    make_characters(7)
    baseline, phases = clean_run(seed=9)
    expected = comparable(baseline)
    assert {"night_wolf_chat", "discussion", "vote", "day_notes"} <= set(phases)
    assert phases.count("night_wolf_chat") >= 1 and phases.count("discussion") >= 3
    for crash_at in range(1, len(phases) + 1):
        resumed = crash_then_resume(9, crash_at, monkeypatch)
        assert_contiguous(resumed)
        assert comparable(resumed) == expected, f"crash at turn {crash_at}"
        assert resumed.day_number == baseline.day_number
        assert resumed.phase == baseline.phase


def test_resume_after_moderator_pick_does_not_call_moderator_again(monkeypatch):
    make_characters(7)
    baseline, phases = clean_run(seed=9)
    first_discussion = phases.index("discussion") + 1
    resumed = crash_then_resume(9, first_discussion + 1, monkeypatch)
    assert len(events_of(resumed, type="moderator_pick")) == len(
        events_of(baseline, type="moderator_pick")
    )
    assert AgentCall.objects.filter(game=resumed, player=None).count() == (
        AgentCall.objects.filter(game=baseline, player=None).count()
    )
