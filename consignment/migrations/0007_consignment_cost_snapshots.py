import django.core.validators
from django.db import migrations, models


def populate_cost_snapshots(apps, schema_editor):
    for model_name, product_field in (
        ("CDConsignmentStock", "cd"),
        ("TechConsignmentStock", "tech"),
    ):
        model = apps.get_model("consignment", model_name)
        for stock in model.objects.select_related(product_field).iterator():
            stock.unit_cost = getattr(stock, product_field).cost
            stock.save(update_fields=("unit_cost",))

    movement_item = apps.get_model("consignment", "ConsignmentMovementItem")
    for item in movement_item.objects.select_related("cd", "tech").iterator():
        product = item.cd if item.product_kind == "cd" else item.tech
        item.unit_cost_snapshot = product.cost
        item.save(update_fields=("unit_cost_snapshot",))


class Migration(migrations.Migration):
    dependencies = [("consignment", "0006_consignment_lots")]

    operations = [
        migrations.AddField(
            model_name="cdconsignmentstock",
            name="unit_cost",
            field=models.DecimalField(
                "Себестоимость единицы партии", max_digits=20, decimal_places=2,
                default=0, validators=[django.core.validators.MinValueValidator(0)], editable=False,
            ),
        ),
        migrations.AddField(
            model_name="consignmentmovementitem",
            name="unit_cost_snapshot",
            field=models.DecimalField(
                "Себестоимость единицы", max_digits=20, decimal_places=2,
                default=0, validators=[django.core.validators.MinValueValidator(0)], editable=False,
            ),
        ),
        migrations.AddField(
            model_name="techconsignmentstock",
            name="unit_cost",
            field=models.DecimalField(
                "Себестоимость единицы партии", max_digits=20, decimal_places=2,
                default=0, validators=[django.core.validators.MinValueValidator(0)], editable=False,
            ),
        ),
        migrations.RunPython(populate_cost_snapshots, migrations.RunPython.noop),
    ]
