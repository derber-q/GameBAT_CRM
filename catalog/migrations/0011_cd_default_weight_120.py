from django.db import migrations, models
import django.core.validators


def update_cd_weight_to_120(apps, schema_editor):
    CD = apps.get_model("catalog", "CD")
    CD.objects.filter(weight_grams=140).update(weight_grams=120)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_rename_retail_price_to_avito_price"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cd",
            name="weight_grams",
            field=models.PositiveIntegerField(
                blank=True,
                default=120,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Вес, г",
            ),
        ),
        migrations.RunPython(update_cd_weight_to_120, migrations.RunPython.noop),
    ]
