import django.core.validators
from django.db import migrations, models


def populate_cost_snapshots(apps, schema_editor):
    for model_name, product_field in (
        ("CDWarehouseTransferItem", "cd"),
        ("TechWarehouseTransferItem", "tech"),
    ):
        model = apps.get_model("warehouse", model_name)
        for item in model.objects.select_related(product_field).iterator():
            item.unit_cost_snapshot = getattr(item, product_field).cost
            item.save(update_fields=("unit_cost_snapshot",))


class Migration(migrations.Migration):
    dependencies = [("warehouse", "0004_alter_warehouse_options_warehousestoragelocation_and_more")]

    operations = [
        migrations.AddField(
            model_name="cdwarehousetransferitem",
            name="unit_cost_snapshot",
            field=models.DecimalField(
                "Себестоимость единицы", max_digits=20, decimal_places=2,
                default=0, validators=[django.core.validators.MinValueValidator(0)], editable=False,
            ),
        ),
        migrations.AddField(
            model_name="techwarehousetransferitem",
            name="unit_cost_snapshot",
            field=models.DecimalField(
                "Себестоимость единицы", max_digits=20, decimal_places=2,
                default=0, validators=[django.core.validators.MinValueValidator(0)], editable=False,
            ),
        ),
        migrations.RunPython(populate_cost_snapshots, migrations.RunPython.noop),
    ]
