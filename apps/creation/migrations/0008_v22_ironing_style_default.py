from django.db import migrations, models


def use_regular_for_legacy_styles(apps, schema_editor):
    GenerationSettings = apps.get_model("creation", "GenerationSettings")
    GenerationSettings.objects.exclude(
        ironing_style__in={
            "waffle", "regular", "towel", "bathcloth", "baking_paper", "glitter"
        }
    ).update(ironing_style="regular")


class Migration(migrations.Migration):
    dependencies = [("creation", "0007_v21_ironing_style")]

    operations = [
        migrations.AlterField(
            model_name="generationsettings",
            name="ironing_style",
            field=models.CharField(default="regular", max_length=40),
        ),
        migrations.RunPython(use_regular_for_legacy_styles, migrations.RunPython.noop),
    ]
