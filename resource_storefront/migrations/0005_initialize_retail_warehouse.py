from django.db import migrations


def configure(apps, schema_editor):
    Warehouse = apps.get_model("warehouse", "Warehouse")
    RetailSettings = apps.get_model("resource_storefront", "RetailSettings")
    alias = schema_editor.connection.alias
    warehouse = Warehouse.objects.using(alias).filter(name="Варфоломеева 265").first()
    RetailSettings.objects.using(alias).get_or_create(pk=1, defaults={"warehouse_id": warehouse.pk if warehouse else None})


class Migration(migrations.Migration):
    dependencies = [("resource_storefront", "0004_retailsettings_retailsubmission")]
    operations = [migrations.RunPython(configure, migrations.RunPython.noop)]
