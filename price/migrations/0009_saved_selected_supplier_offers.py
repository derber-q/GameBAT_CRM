from django.db import migrations


def preserve_selected_offers(apps, schema_editor):
    """Для старых версий сохраняем только достоверную цену выбранного поставщика."""
    Item = apps.get_model("price", "ProcurementPriceListItem")
    Offer = apps.get_model("price", "ProcurementSupplierOffer")
    alias = schema_editor.connection.alias
    for item in Item.objects.using(alias).all().iterator():
        Offer.objects.using(alias).get_or_create(
            price_list_item_id=item.pk, supplier_id=item.selected_supplier_id,
            defaults={"price_aed": item.supplier_price_aed},
        )


class Migration(migrations.Migration):
    dependencies = [("price", "0008_procurementpricelist_supplier_offers_complete_and_more")]
    operations = [migrations.RunPython(preserve_selected_offers, migrations.RunPython.noop)]
