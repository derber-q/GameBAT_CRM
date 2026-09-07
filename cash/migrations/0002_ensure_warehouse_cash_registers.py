from django.db import migrations


def ensure_warehouse_cash_registers(apps, schema_editor):
    Warehouse = apps.get_model("warehouse", "Warehouse")
    CashRegister = apps.get_model("cash", "CashRegister")
    for warehouse_id in Warehouse.objects.values_list("id", flat=True).iterator():
        CashRegister.objects.get_or_create(warehouse_id=warehouse_id)


class Migration(migrations.Migration):
    dependencies = [("cash", "0001_initial")]

    operations = [
        migrations.RunPython(ensure_warehouse_cash_registers, migrations.RunPython.noop),
    ]
