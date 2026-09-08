from django.db import migrations


def ensure_warehouse_safes(apps, schema_editor):
    Warehouse = apps.get_model("warehouse", "Warehouse")
    Safe = apps.get_model("cash", "Safe")
    for warehouse_id in Warehouse.objects.values_list("id", flat=True).iterator():
        Safe.objects.get_or_create(warehouse_id=warehouse_id, defaults={"balance": 0})


class Migration(migrations.Migration):
    dependencies = [("cash", "0003_cashtransaction_operation_key_and_more")]

    operations = [
        migrations.RunPython(ensure_warehouse_safes, migrations.RunPython.noop),
    ]
