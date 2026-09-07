from django.db import migrations
from django.db.models import Sum


WAREHOUSE_NAME = "Варфоломеева 265"


def forwards(apps, schema_editor):
    Warehouse = apps.get_model("warehouse", "Warehouse")
    CDWarehouseStock = apps.get_model("warehouse", "CDWarehouseStock")
    TechWarehouseStock = apps.get_model("warehouse", "TechWarehouseStock")
    CD = apps.get_model("catalog", "CD")
    Tech = apps.get_model("catalog", "Tech")
    warehouse, _ = Warehouse.objects.get_or_create(name=WAREHOUSE_NAME)
    CDWarehouseStock.objects.bulk_create([
        CDWarehouseStock(warehouse=warehouse, cd_id=product.pk, quantity=product.quantity)
        for product in CD.objects.filter(quantity__gt=0)
    ])
    TechWarehouseStock.objects.bulk_create([
        TechWarehouseStock(warehouse=warehouse, tech_id=product.pk, quantity=product.quantity)
        for product in Tech.objects.filter(quantity__gt=0)
    ])


def backwards(apps, schema_editor):
    CDWarehouseStock = apps.get_model("warehouse", "CDWarehouseStock")
    TechWarehouseStock = apps.get_model("warehouse", "TechWarehouseStock")
    CD = apps.get_model("catalog", "CD")
    Tech = apps.get_model("catalog", "Tech")
    for row in CDWarehouseStock.objects.values("cd_id").annotate(total=Sum("quantity")):
        CD.objects.filter(pk=row["cd_id"]).update(quantity=row["total"])
    for row in TechWarehouseStock.objects.values("tech_id").annotate(total=Sum("quantity")):
        Tech.objects.filter(pk=row["tech_id"]).update(quantity=row["total"])


class Migration(migrations.Migration):
    dependencies = [("warehouse", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
