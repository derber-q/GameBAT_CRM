from django.db import migrations, models
from django.db.models.functions import Lower


def merge_case_insensitive_platforms(apps, schema_editor):
    Platform = apps.get_model("catalog", "Platform")
    CD = apps.get_model("catalog", "CD")

    for canonical_name in ("PlayStation 4", "PlayStation 5"):
        rows = list(Platform.objects.filter(name__iexact=canonical_name).order_by("id"))
        if not rows:
            continue
        canonical = next((row for row in rows if row.name == canonical_name), rows[0])
        if canonical.name != canonical_name:
            canonical.name = canonical_name
            canonical.save(update_fields=["name"])
        for duplicate in rows:
            if duplicate.pk == canonical.pk:
                continue
            CD.objects.filter(platform_id=duplicate.pk).update(platform_id=canonical.pk)
            duplicate.delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0018_price_markups_189")]

    operations = [
        migrations.RunPython(merge_case_insensitive_platforms, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="platform",
            constraint=models.UniqueConstraint(
                Lower("name"), name="platform_name_ci_unique"
            ),
        ),
    ]
