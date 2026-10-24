from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from werewolf.models import Character

CAST = [
    ("Margaret", 3),
    ("Reginald", 5),
    ("Dorothy", 2),
    ("Barnaby", 4),
    ("Edith", 1),
    ("Cuthbert", 3),
    ("Pippa", 5),
]


class Command(BaseCommand):
    help = "Create the werewolf cast (idempotent)."

    def handle(self, *args, **options):
        sprites = sorted((Path(settings.MEDIA_ROOT) / "sprites").glob("*.png"))
        created = 0
        for i, (name, talk) in enumerate(CAST):
            if Character.objects.filter(name=name).exists():
                continue
            character = Character(name=name, talkativeness=talk)
            if sprites:
                sprite = sprites[i % len(sprites)]
                with sprite.open("rb") as fh:
                    character.avatar.save(sprite.name, File(fh), save=False)
            character.save()
            created += 1
        self.stdout.write(f"Created {created} characters ({len(CAST)} in cast).")
