from werewolf.models import Character, Game


def make_characters(n=7):
    return [
        Character.objects.create(name=f"Char{i}", talkativeness=(i % 5) + 1)
        for i in range(n)
    ]


def make_game(**kwargs):
    kwargs.setdefault("seed", 1)
    return Game.objects.create(**kwargs)
