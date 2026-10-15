from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0027_default_fbs_desired_profit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cd",
            name="yandex_desired_profit",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=Decimal("500.00"),
                max_digits=20, null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Желаемая чистая прибыль, ₽",
            ),
        ),
        migrations.AlterField(
            model_name="tech",
            name="yandex_desired_profit",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=20, null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Желаемая чистая прибыль, ₽",
            ),
        ),
    ]
