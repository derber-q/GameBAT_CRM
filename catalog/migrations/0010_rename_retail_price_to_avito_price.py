import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0009_barcode_registry")]

    operations = [
        migrations.RemoveConstraint(model_name="cd", name="cd_retail_price_nonnegative"),
        migrations.RemoveConstraint(model_name="tech", name="tech_retail_price_nonnegative"),
        migrations.RenameField(model_name="cd", old_name="retail_price", new_name="avito_price"),
        migrations.RenameField(model_name="tech", old_name="retail_price", new_name="avito_price"),
        migrations.AlterField(
            model_name="cd",
            name="avito_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=20, null=True,
                validators=[django.core.validators.MinValueValidator(0)], verbose_name="Цена Avito",
            ),
        ),
        migrations.AlterField(
            model_name="tech",
            name="avito_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=20, null=True,
                validators=[django.core.validators.MinValueValidator(0)], verbose_name="Цена Avito",
            ),
        ),
        migrations.AddConstraint(
            model_name="cd",
            constraint=models.CheckConstraint(
                condition=models.Q(avito_price__gte=0) | models.Q(avito_price__isnull=True),
                name="cd_avito_price_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="tech",
            constraint=models.CheckConstraint(
                condition=models.Q(avito_price__gte=0) | models.Q(avito_price__isnull=True),
                name="tech_avito_price_nonnegative",
            ),
        ),
    ]
