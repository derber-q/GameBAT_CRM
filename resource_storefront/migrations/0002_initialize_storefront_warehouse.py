from django.db import migrations


def configure_known_warehouse(apps, schema_editor):
    Settings = apps.get_model("resource_storefront", "StorefrontSettings")
    Warehouse = apps.get_model("warehouse", "Warehouse")
    matches = list(Warehouse.objects.using(schema_editor.connection.alias).filter(name="Варфоломеева 265").values_list("pk", flat=True))
    config, _ = Settings.objects.using(schema_editor.connection.alias).get_or_create(pk=1)
    # Only preselect a uniquely identified known warehouse. Ambiguous or missing names require staff setup.
    if len(matches) == 1:
        config.warehouse_id = matches[0]
        config.save(update_fields=("warehouse",))


class Migration(migrations.Migration):
    dependencies = [
        ("resource_storefront", "0001_initial"),
        ("warehouse", "0005_transfer_cost_snapshots"),
    ]

    operations = [migrations.RunPython(configure_known_warehouse, migrations.RunPython.noop)]
