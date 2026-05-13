import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0008_populate_default_instance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agent",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="agents",
                to="world.instance",
            ),
        ),
        migrations.AlterField(
            model_name="location",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="locations",
                to="world.instance",
            ),
        ),
        migrations.AlterField(
            model_name="tick",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ticks",
                to="world.instance",
            ),
        ),
    ]
