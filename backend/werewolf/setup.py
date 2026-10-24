import random

from django.db import transaction

from werewolf.config import build_config
from werewolf.events import append_event
from werewolf.models import Character, Game, Player, player_visibility
from werewolf.rng import rng_for

PLAYER_COUNT = 7
ROLE_DECK = ["wolf"] * 2 + ["seer"] + ["villager"] * 4
WOLF_LABELS = ["Wolf A", "Wolf B"]

WIN_CONDITIONS = {
    "wolf": "Win when the wolves equal or outnumber everyone else.",
    "seer": "Win when every wolf has been eliminated.",
    "villager": "Win when every wolf has been eliminated.",
}


@transaction.atomic
def create_game(seed=None, config=None, published=False) -> Game:
    cfg = build_config(config)
    characters = list(Character.objects.order_by("name"))
    if len(characters) < PLAYER_COUNT:
        raise ValueError(
            f"Need at least {PLAYER_COUNT} characters, found {len(characters)}"
        )
    if seed is None:
        seed = random.SystemRandom().randrange(2**31)

    game = Game.objects.create(
        seed=seed,
        status=Game.Status.ACTIVE,
        phase=Game.Phase.NIGHT_WOLF_CHAT,
        day_number=1,
        config=cfg,
        published=published,
    )
    cast = rng_for(game, "cast").sample(characters, PLAYER_COUNT)
    roles = list(ROLE_DECK)
    rng_for(game, "roles").shuffle(roles)

    labels = iter(WOLF_LABELS)
    players = [
        Player.objects.create(
            game=game,
            character=character,
            seat=seat,
            role=role,
            wolf_label=next(labels) if role == Player.Role.WOLF else None,
        )
        for seat, (character, role) in enumerate(zip(cast, roles, strict=True))
    ]

    wolves = [p for p in players if p.role == Player.Role.WOLF]
    for player in players:
        payload = {"role": player.role, "win_condition": WIN_CONDITIONS[player.role]}
        if player.role == Player.Role.WOLF:
            (mate,) = [w for w in wolves if w.pk != player.pk]
            payload.update(
                wolf_label=player.wolf_label,
                teammate_name=mate.character.name,
                teammate_label=mate.wolf_label,
            )
        append_event(
            game,
            type="role_assigned",
            visibility=player_visibility(player.pk),
            actor=player,
            payload=payload,
        )
    return game
