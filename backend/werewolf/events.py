from django.db import transaction
from django.db.models import Max

from werewolf.models import Game, GameEvent


def append_event(
    game, *, type, visibility, day=None, phase=None, actor=None, payload=None
) -> GameEvent:
    """Append an event with the next per-game seq, atomically."""
    with transaction.atomic():
        locked = Game.objects.select_for_update().get(pk=game.pk)
        last = GameEvent.objects.filter(game=locked).aggregate(m=Max("seq"))["m"]
        return GameEvent.objects.create(
            game=locked,
            seq=(last or 0) + 1,
            day=locked.day_number if day is None else day,
            phase=locked.phase if phase is None else phase,
            type=type,
            visibility=visibility,
            actor=actor,
            payload=payload or {},
        )
