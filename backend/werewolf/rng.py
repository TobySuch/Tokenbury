import hashlib
import random


def rng_for(game, *parts) -> random.Random:
    """Deterministic RNG for (game seed, parts); stable across processes."""
    key = f"{game.seed}:" + ":".join(str(p) for p in parts)
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest(), 16))
