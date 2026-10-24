from werewolf.models import Character, Game
from werewolf.setup import create_game


def make_characters(n=7):
    return [
        Character.objects.create(name=f"Char{i}", talkativeness=(i % 5) + 1)
        for i in range(n)
    ]


def make_game(**kwargs):
    kwargs.setdefault("seed", 1)
    return Game.objects.create(**kwargs)


def classic_config(**overrides):
    """Config for a classic game: 2 wolves, 1 seer, 4 villagers, no lovers.

    The engine doesn't act on the doctor or lovers yet, so tests that run the
    engine/prompts/visibility use this instead of the (richer) defaults.
    """
    return {"doctor_count": 0, "lovers": False, **overrides}


def create_classic_game(seed=None, config=None, **kwargs):
    return create_game(seed=seed, config=classic_config(**(config or {})), **kwargs)
