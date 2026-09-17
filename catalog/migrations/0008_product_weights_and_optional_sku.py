import django.core.validators
from django.db import migrations, models


def set_existing_cd_weight(apps, schema_editor):
    CD = apps.get_model("catalog", "CD")
    CD.objects.filter(weight_grams__isnull=True).update(weight_grams=140)


def clear_cd_weight(apps, schema_editor):
    CD = apps.get_model("catalog", "CD")
    CD.objects.update(weight_grams=None)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0007_alter_cd_barcode_alter_tech_barcode")]

    operations = [
        migrations.AddField(
            model_name="cd",
            name="weight_grams",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Вес, г",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AddField(
            model_name="tech",
            name="weight_grams",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Вес, г",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.RunPython(set_existing_cd_weight, clear_cd_weight),
        migrations.AlterField(
            model_name="cd",
            name="weight_grams",
            field=models.PositiveIntegerField(
                blank=True, default=140, verbose_name="Вес, г",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name="cd",
            name="sku",
            field=models.CharField(blank=True, max_length=100, verbose_name="Артикул"),
        ),
        migrations.AlterField(
            model_name="tech",
            name="sku",
            field=models.CharField(blank=True, max_length=100, verbose_name="Артикул"),
        ),
        migrations.AlterModelOptions(
            name="cd",
            options={
                "ordering": ("name", "id"),
                "permissions": [
                    ("view_nomenclature", "Номенклатура: просмотр"),
                    ("change_cd_platform", "CD: изменение платформы"),
                    ("change_cd_name", "CD: изменение названия"),
                    ("change_cd_description", "CD: изменение описания"),
                    ("change_cd_sku", "CD: изменение артикула"),
                    ("change_cd_barcode", "CD: изменение штрихкода"),
                    ("change_cd_weight", "CD: изменение веса"),
                    ("change_cd_cusa_ppsa_code", "CD: изменение CUSA/PPSA"),
                    ("change_cd_comment", "CD: изменение комментария"),
                ],
                "verbose_name": "CD",
                "verbose_name_plural": "CD",
            },
        ),
        migrations.AlterModelOptions(
            name="tech",
            options={
                "ordering": ("name", "id"),
                "permissions": [
                    ("change_tech_brand", "Tech: изменение бренда"),
                    ("change_tech_product_type", "Tech: изменение типа товара"),
                    ("change_tech_name", "Tech: изменение названия"),
                    ("change_tech_description", "Tech: изменение описания"),
                    ("change_tech_sku", "Tech: изменение артикула"),
                    ("change_tech_barcode", "Tech: изменение штрихкода"),
                    ("change_tech_weight", "Tech: изменение веса"),
                    ("change_tech_comment", "Tech: изменение комментария"),
                ],
                "verbose_name": "техника",
                "verbose_name_plural": "техника",
            },
        ),
        migrations.AddConstraint(
            model_name="cd",
            constraint=models.CheckConstraint(
                condition=models.Q(weight_grams__gt=0), name="cd_weight_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="tech",
            constraint=models.CheckConstraint(
                condition=models.Q(weight_grams__gt=0) | models.Q(weight_grams__isnull=True),
                name="tech_weight_positive_or_null",
            ),
        ),
    ]
