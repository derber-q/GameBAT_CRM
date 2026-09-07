from django.db import migrations, models
import django.db.models.deletion


WAREHOUSE_NAME = "Варфоломеева 265"


def assign_existing_supplies(apps, schema_editor):
    Supply = apps.get_model("supplies", "Supply")
    Warehouse = apps.get_model("warehouse", "Warehouse")
    warehouse, _ = Warehouse.objects.get_or_create(name=WAREHOUSE_NAME)
    Supply.objects.filter(warehouse__isnull=True).update(warehouse=warehouse)


class Migration(migrations.Migration):
    dependencies = [
        ("supplies", "0002_supplycditem_supply_cd_allocated_nonnegative_and_more"),
        ("warehouse", "0003_transfers"),
    ]
    operations = [
        migrations.AddField(
            model_name="supply",
            name="warehouse",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplies", to="warehouse.warehouse", verbose_name="Склад поступления"),
        ),
        migrations.RunPython(assign_existing_supplies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supply",
            name="warehouse",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplies", to="warehouse.warehouse", verbose_name="Склад поступления"),
        ),
    ]
