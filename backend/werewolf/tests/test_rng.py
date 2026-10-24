import subprocess
import sys

from werewolf.rng import rng_for


class G:
    seed = 42


def test_deterministic():
    assert rng_for(G, "a", "b").random() == rng_for(G, "a", "b").random()


def test_parts_differ():
    assert rng_for(G, "a").random() != rng_for(G, "b").random()


def test_stable_value():
    # pinned so a change in algorithm (breaking replay) is noticed
    import hashlib
    import random

    expected = random.Random(int(hashlib.sha256(b"42:a:b").hexdigest(), 16)).random()
    assert rng_for(G, "a", "b").random() == expected


def test_stable_across_processes():
    code = (
        "from werewolf.rng import rng_for\n"
        "class G: seed=42\n"
        "print(rng_for(G,'a','b').random())"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert float(out) == rng_for(G, "a", "b").random()
