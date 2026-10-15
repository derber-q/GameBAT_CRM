from django.db import migrations


def initialize(apps, schema_editor):
    from catalog.product_identifiers import allocate_unique_barcode

    product_model = apps.get_model("catalog", "SystemProduct")
    registry_model = apps.get_model("catalog", "BarcodeRegistry")
    for kind in ("DIGITAL_PRODUCT", "EXPENSE"):
        product, _ = product_model.objects.get_or_create(kind=kind)
        if not registry_model.objects.filter(system_product=product).exists():
            allocate_unique_barcode(registry_model, product_kind="system", system_product=product)


def uninitialize(apps, schema_editor):
    # Откат следующей операции удаляет SystemProduct из схемы; сначала освобождаем
    # только его регистрации, иначе прежнее ограничение CD/Tech нельзя вернуть.
    apps.get_model("catalog", "BarcodeRegistry").objects.filter(product_kind="system").delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0030_systemproduct_and_more")]
    operations = [migrations.RunPython(initialize, uninitialize)]
