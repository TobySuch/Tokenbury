import itertools
import random
import string

from django.db import transaction

from werewolf.config import build_config, role_counts
from werewolf.events import append_event
from werewolf.models import Character, Game, Player, player_visibility
from werewolf.rng import rng_for

WOLF_WIN = "Win when the wolves equal or outnumber everyone else."
TOWN_WIN = "Win when every wolf has been eliminated."
WIN_CONDITIONS = {
    "wolf": WOLF_WIN,
    "seer": TOWN_WIN,
    "doctor": TOWN_WIN,
    "villager": TOWN_WIN,
}

LOVERS_NOTE = (
    "{name} is your secret lover. If either of you dies, the other dies "
    "of a broken heart at once. If your partner turns out to be on the other "
    "side, you can also win by being the last two left alive."
)


def wolf_label(index: int) -> str:
    return f"Wolf {string.ascii_uppercase[index]}"


def _pick_lovers(game, players):
    pairs = [
        pair
        for pair in itertools.combinations(players, 2)
        if not all(p.role == Player.Role.WOLF for p in pair)
    ]
    return rng_for(game, "lovers").choice(pairs)


@transaction.atomic
def create_game(seed=None, config=None, published=False) -> Game:
    cfg = build_config(config)
    player_count = cfg["player_count"]
    characters = list(Character.objects.order_by("name"))
    if len(characters) < player_count:
        raise ValueError(
            f"Need at least {player_count} characters, found {len(characters)}. "
            "Run `manage.py seed_werewolf_characters`."
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
    cast = rng_for(game, "cast").sample(characters, player_count)
    roles = [role for role, n in role_counts(cfg).items() for _ in range(n)]
    rng_for(game, "roles").shuffle(roles)

    wolf_index = itertools.count()
    players = [
        Player.objects.create(
            game=game,
            character=character,
            seat=seat,
            role=role,
            wolf_label=(
                wolf_label(next(wolf_index)) if role == Player.Role.WOLF else None
            ),
        )
        for seat, (character, role) in enumerate(zip(cast, roles, strict=True))
    ]

    if cfg["lovers"]:
        a, b = _pick_lovers(game, players)
        a.lover, b.lover = b, a
        a.save(update_fields=["lover"])
        b.save(update_fields=["lover"])

    wolves = [p for p in players if p.role == Player.Role.WOLF]
    for player in players:
        payload = {"role": player.role, "win_condition": WIN_CONDITIONS[player.role]}
        if player.role == Player.Role.WOLF:
            payload.update(
                wolf_label=player.wolf_label,
                teammates=[
                    {"name": w.character.name, "label": w.wolf_label}
                    for w in wolves
                    if w.pk != player.pk
                ],
            )
        if player.lover:
            payload.update(
                lover_name=player.lover.character.name,
                lovers_note=LOVERS_NOTE.format(name=player.lover.character.name),
            )
        append_event(
            game,
            type="role_assigned",
            visibility=player_visibility(player.pk),
            actor=player,
            payload=payload,
        )
    return game
