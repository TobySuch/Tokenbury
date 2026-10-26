import datetime

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from werewolf.models import AgentCall, Character, Game, GameEvent
from werewolf.tests.factories import create_classic_game, make_characters


@pytest.fixture(autouse=True)
def media(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    # Isolate from a real run_day holding the global lock.
    monkeypatch.setattr(
        "werewolf.management.commands.run_day.LOCK_FILE", str(tmp_path / "lock")
    )


@pytest.fixture
def media_root(tmp_path, settings):
    """Isolated MEDIA_ROOT so tests never depend on (or write to) the real media/."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _make_sprites(media_root, n=2):
    sprites = media_root / "sprites"
    sprites.mkdir()
    for i in range(n):
        (sprites / f"sprite{i}.png").write_bytes(b"\x89PNG fake")


def test_seed_creates_twelve_idempotently(db, media_root):
    _make_sprites(media_root)
    call_command("seed_werewolf_characters")
    assert Character.objects.count() == 12
    call_command("seed_werewolf_characters")
    assert Character.objects.count() == 12
    talk = {c.talkativeness for c in Character.objects.all()}
    assert talk == {1, 2, 3, 4, 5} and all(1 <= t <= 5 for t in talk)
    assert all(c.avatar for c in Character.objects.all())
    assert all((media_root / c.avatar.name).exists() for c in Character.objects.all())


def test_seed_without_sprites_creates_characters_without_avatars(db, media_root):
    call_command("seed_werewolf_characters")
    assert Character.objects.count() == 12
    assert not any(c.avatar for c in Character.objects.all())


def test_create_game_command(db):
    make_characters(7)
    call_command("create_werewolf_game", "--seed", "11", "--config", "max_days=3")
    game = Game.objects.get()
    assert game.seed == 11
    assert game.config["max_days"] == 3
    assert game.players.count() == 7


def test_create_game_command_player_count_override(db):
    make_characters(12)
    call_command(
        "create_werewolf_game", "--config", "player_count=10", "wolf_count=null"
    )
    game = Game.objects.get()
    assert game.config["player_count"] == 10
    assert game.players.count() == 10
    assert game.players.filter(role="wolf").count() == 3


def test_create_game_command_invalid_mix(db):
    make_characters(12)
    with pytest.raises(CommandError, match="wolf"):
        call_command("create_werewolf_game", "--config", "wolf_count=0")
    assert not Game.objects.exists()


def test_create_game_command_bad_config(db):
    make_characters(7)
    with pytest.raises(CommandError):
        call_command("create_werewolf_game", "--config", "bogus=1")
    with pytest.raises(CommandError):
        call_command("create_werewolf_game", "--config", "noequals")


def test_create_game_command_too_few_characters(db):
    with pytest.raises(CommandError):
        call_command("create_werewolf_game")


# ------------------------------------------------------------- run_day

RUN_DAY = "werewolf.management.commands.run_day"


def at_hour(monkeypatch, hour, day=None):
    base = timezone.localtime().replace(hour=hour, minute=0, second=0, microsecond=0)
    if day:
        base = base.replace(day=day)
    monkeypatch.setattr(f"{RUN_DAY}.now_local", lambda: base)
    return base


def test_run_day_scripted_until_over_finishes_game(db, capsys):
    make_characters(7)
    game = create_classic_game(seed=7, published=True)
    call_command("run_day", "--scripted", "--until-over")
    game.refresh_from_db()
    assert game.status == "finished"
    assert game.winner in {"wolves", "town", "draw"}
    out = capsys.readouterr().out
    assert "Winner" in out and game.winner in out
    assert "calls" in out.lower()


def test_run_day_skips_finished_games(db):
    make_characters(7)
    old = create_classic_game(seed=1, published=True)
    old.status = "finished"
    old.save()
    game = create_classic_game(seed=2, published=True)
    call_command("run_day", "--scripted")
    game.refresh_from_db()
    assert game.day_number == 2 and game.phase == "night_wolf_chat"
    old.refresh_from_db()
    assert not GameEvent.objects.filter(game=old, type="wolf_message").exists()


def test_run_day_default_runs_all_published_active_games(db):
    make_characters(7)
    finished = create_classic_game(seed=1, published=True)
    finished.status = "finished"
    finished.save()
    first = create_classic_game(seed=2, published=True)
    second = create_classic_game(seed=3, published=True)
    call_command("run_day", "--scripted")
    for game in (first, second):
        game.refresh_from_db()
        assert game.day_number == 2 and game.phase == "night_wolf_chat"
    assert not GameEvent.objects.filter(game=finished, type="wolf_message").exists()


def test_if_due_is_checked_per_game(db, monkeypatch, settings, capsys):
    settings.WEREWOLF_RUN_HOUR = 9
    make_characters(7)
    played = create_classic_game(seed=2, published=True)
    at_hour(monkeypatch, 10)
    call_command("run_day", "--scripted", "--if-due")
    fresh = create_classic_game(seed=3, published=True)
    call_command("run_day", "--scripted", "--if-due")
    played.refresh_from_db()
    fresh.refresh_from_db()
    assert played.day_number == 2
    assert fresh.day_number == 2
    assert f"game {played.pk} not due" in capsys.readouterr().out.lower()


def test_run_day_game_option(db):
    make_characters(7)
    first = create_classic_game(seed=1)
    create_classic_game(seed=2)
    call_command("run_day", "--scripted", "--game", str(first.pk))
    first.refresh_from_db()
    assert first.day_number == 2


def test_run_day_unknown_game(db):
    with pytest.raises(CommandError):
        call_command("run_day", "--scripted", "--game", "999")


def test_run_day_without_active_game_is_not_an_error(db, capsys):
    call_command("run_day", "--scripted")
    assert "no published active game" in capsys.readouterr().out.lower()


def test_if_due_skips_before_run_hour(db, monkeypatch, settings):
    settings.WEREWOLF_RUN_HOUR = 9
    make_characters(7)
    game = create_classic_game(seed=3, published=True)
    at_hour(monkeypatch, 8)
    call_command("run_day", "--scripted", "--if-due")
    game.refresh_from_db()
    assert game.day_number == 1 and not AgentCall.objects.exists()


def test_if_due_runs_after_hour_then_skips_when_already_run_today(
    db, monkeypatch, settings, capsys
):
    settings.WEREWOLF_RUN_HOUR = 9
    make_characters(7)
    game = create_classic_game(seed=3, published=True)
    at_hour(monkeypatch, 10)
    call_command("run_day", "--scripted", "--if-due")
    game.refresh_from_db()
    assert game.day_number == 2
    calls = AgentCall.objects.count()
    call_command("run_day", "--scripted", "--if-due")
    game.refresh_from_db()
    assert game.day_number == 2 and AgentCall.objects.count() == calls
    assert "already" in capsys.readouterr().out.lower()


def test_if_due_runs_again_next_day(db, monkeypatch, settings):
    settings.WEREWOLF_RUN_HOUR = 9
    make_characters(7)
    game = create_classic_game(seed=3, published=True)
    now = at_hour(monkeypatch, 10)
    call_command("run_day", "--scripted", "--if-due")
    GameEvent.objects.filter(game=game).update(
        created_at=now - datetime.timedelta(days=1)
    )
    call_command("run_day", "--scripted", "--if-due")
    game.refresh_from_db()
    assert game.day_number == 3 or game.status == "finished"


def test_create_game_command_is_unpublished_unless_publish_flag(db):
    make_characters(7)
    call_command("create_werewolf_game", "--seed", "1")
    call_command("create_werewolf_game", "--seed", "2", "--publish")
    assert list(Game.objects.order_by("seed").values_list("published", flat=True)) == [
        False,
        True,
    ]


def test_run_day_default_ignores_unpublished_games(db, capsys):
    make_characters(7)
    live = create_classic_game(seed=1, published=True)
    draft = create_classic_game(seed=2)
    call_command("run_day", "--scripted")
    live.refresh_from_db()
    draft.refresh_from_db()
    assert live.day_number == 2
    assert draft.day_number == 1
    assert not GameEvent.objects.filter(game=draft, type="wolf_message").exists()


def test_run_day_with_only_unpublished_games_does_nothing(db, capsys):
    make_characters(7)
    draft = create_classic_game(seed=2)
    call_command("run_day", "--scripted")
    draft.refresh_from_db()
    assert draft.day_number == 1
    assert "no published active game" in capsys.readouterr().out.lower()


def test_run_day_game_option_can_run_an_unpublished_game(db):
    make_characters(7)
    draft = create_classic_game(seed=2)
    call_command("run_day", "--scripted", "--game", str(draft.pk))
    draft.refresh_from_db()
    assert draft.day_number == 2


def test_run_hour_defaults_to_midnight():
    from django.conf import settings

    assert settings.WEREWOLF_RUN_HOUR == 0


def test_if_due_runs_just_after_midnight_by_default(db, monkeypatch):
    make_characters(7)
    game = create_classic_game(seed=3, published=True)
    at_hour(monkeypatch, 0)
    call_command("run_day", "--scripted", "--if-due")
    game.refresh_from_db()
    assert game.day_number == 2
