from decimal import Decimal

from django.db import migrations, models


def _copy_source_value(apps, schema_editor, field_name):
    Preference = apps.get_model("price", "ProcurementPricePreference")
    Item = apps.get_model("price", "ProcurementPriceListItem")
    alias = schema_editor.connection.alias
    for preference in Preference.objects.using(alias).select_related("source_item").iterator():
        item = preference.source_item
        if item is None:
            item = Item.objects.using(alias).filter(
                cd_id=preference.cd_id, tech_id=preference.tech_id,
            ).order_by("-price_list__created_at", "-price_list_id", "-id").first()
        # Сумму прежней итоговой цены нельзя использовать как наценку.
        preference.markup_rub = getattr(item, field_name) if item is not None else Decimal("0.00")
        preference.save(using=alias, update_fields=("markup_rub",))


def remember_markup(apps, schema_editor):
    _copy_source_value(apps, schema_editor, "markup_rub")


def restore_final_price(apps, schema_editor):
    _copy_source_value(apps, schema_editor, "prepayment_price_rub")


class Migration(migrations.Migration):
    dependencies = [("price", "0005_remembered_prices_and_negative_markup")]

    operations = [
        migrations.RemoveConstraint(model_name="procurementpricepreference", name="proc_preference_nonnegative"),
        migrations.RenameField(model_name="procurementpricepreference", old_name="prepayment_price_rub", new_name="markup_rub"),
        migrations.AlterField(
            model_name="procurementpricepreference", name="markup_rub",
            field=models.DecimalField(decimal_places=2, max_digits=20, verbose_name="Сохранённая наценка, RUB"),
        ),
        migrations.AlterModelOptions(
            name="procurementpricepreference",
            options={"verbose_name": "сохранённая наценка закупочного прайса", "verbose_name_plural": "сохранённые наценки закупочного прайса"},
        ),
        migrations.RunPython(remember_markup, restore_final_price),
    ]
