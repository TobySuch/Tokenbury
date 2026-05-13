import os
import shutil

from django.conf import settings
from django.db import migrations


def populate_default_instance(apps, schema_editor):
    Agent = apps.get_model("world", "Agent")
    Location = apps.get_model("world", "Location")
    Tick = apps.get_model("world", "Tick")
    Instance = apps.get_model("world", "Instance")

    # No-op for fresh installs with no existing data
    if (
        not Agent.objects.exists()
        and not Location.objects.exists()
        and not Tick.objects.exists()
    ):
        return

    # Copy existing frontend map asset into Django media
    src = (
        settings.BASE_DIR.parent / "frontend" / "public" / "assets" / "map" / "town.png"
    )
    maps_dir = settings.MEDIA_ROOT / "maps"
    os.makedirs(maps_dir, exist_ok=True)
    dest = maps_dir / "town.png"
    if src.exists() and not dest.exists():
        shutil.copy2(src, dest)

    instance = Instance.objects.create(
        name="Tokenbury-on-Sea",
        slug="tokenbury-on-sea",
        map_image="maps/town.png",
        active=True,
    )

    Agent.objects.update(instance=instance)
    Location.objects.update(instance=instance)
    Tick.objects.update(instance=instance)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("world", "0007_instance_model_and_nullable_fks")]

    operations = [
        migrations.RunPython(populate_default_instance, noop_reverse),
    ]
