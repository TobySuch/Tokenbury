from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0003_tick_agenttick"),
    ]

    operations = [
        migrations.AddField(
            model_name="tick",
            name="active",
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]
