from django.db import transaction
from django.db.models import Max

from werewolf.config import game_config
from werewolf.models import GameEvent, PlayerNotes


class NotesError(ValueError):
    pass


def _latest(player):
    return PlayerNotes.objects.filter(player=player).order_by("-version").first()


def current_notes(player) -> str:
    latest = _latest(player)
    return latest.text if latest else ""


def _write(player, text) -> PlayerNotes:
    with transaction.atomic():
        latest = _latest(player)
        at_seq = (
            GameEvent.objects.filter(game_id=player.game_id).aggregate(m=Max("seq"))[
                "m"
            ]
            or 0
        )
        return PlayerNotes.objects.create(
            game_id=player.game_id,
            player=player,
            version=(latest.version if latest else 0) + 1,
            text=text,
            at_seq=at_seq,
        )


def append_note(player, text) -> PlayerNotes:
    text = text.strip()
    if not text:
        raise NotesError("Note text must not be empty")
    existing = current_notes(player)
    new = f"{existing}\n{text}" if existing else text
    cap = game_config(player.game)["notes_max_chars"]
    if len(new) > cap:
        remaining = max(cap - len(existing) - (1 if existing else 0), 0)
        raise NotesError(f"Note too long: {remaining} characters remaining")
    return _write(player, new)


def replace_notes(player, text) -> PlayerNotes:
    text = text.strip()
    if not text:
        raise NotesError("Notes text must not be empty")
    cap = game_config(player.game)["notes_max_chars"]
    if len(text) > cap:
        raise NotesError(f"Notes too long: {cap} characters remaining")
    return _write(player, text)


def notes_as_of(player, at_seq) -> PlayerNotes | None:
    return (
        PlayerNotes.objects
        .filter(player=player, at_seq__lte=at_seq)
        .order_by("-version")
        .first()
    )
