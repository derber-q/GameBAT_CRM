from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import migrations, models


CENT = Decimal("0.01")


def round_existing_costs(apps, schema_editor):
    for model_name in ("CD", "Tech"):
        product_model = apps.get_model("catalog", model_name)
        for product in product_model.objects.only("pk", "cost").iterator():
            rounded_cost = Decimal(product.cost).quantize(CENT, rounding=ROUND_HALF_UP)
            product_model.objects.filter(pk=product.pk).update(cost=rounded_cost)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_multiwarehouse_and_pricing")]

    operations = [
        migrations.AlterField(
            model_name="cd",
            name="cost",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=20,
                validators=[MinValueValidator(0)],
                verbose_name="Средняя себестоимость",
            ),
        ),
        migrations.AlterField(
            model_name="tech",
            name="cost",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=20,
                validators=[MinValueValidator(0)],
                verbose_name="Средняя себестоимость",
            ),
        ),
        migrations.RunPython(round_existing_costs, migrations.RunPython.noop),
    ]
