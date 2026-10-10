from django.db import migrations, models
from django.db.models import Q


def initialize_stock_history(apps, schema_editor):
    """Отмечает только подтверждённый положительный физический остаток."""
    database = schema_editor.connection.alias
    changes = apps.get_model("catalog", "ProductFieldChange").objects.using(database).filter(
        Q(field_name__startswith="warehouse_stock_") | Q(field_name="quantity"),
    ).filter(
        Q(old_value__regex=r"^[1-9][0-9]*$") | Q(new_value__regex=r"^[1-9][0-9]*$"),
    )
    for kind, model_name, stock_name in (
        ("cd", "CD", "CDWarehouseStock"), ("tech", "Tech", "TechWarehouseStock"),
    ):
        product_model = apps.get_model("catalog", model_name)
        stock_model = apps.get_model("warehouse", stock_name)
        product_ids = set(stock_model.objects.using(database).filter(quantity__gt=0).values_list(
            f"{kind}_id", flat=True,
        ))
        product_ids.update(changes.filter(event__product_kind=kind).values_list(f"event__{kind}_id", flat=True))
        # Меняется только служебный признак. Количества, цены и очередь Avito не затрагиваются.
        product_model.objects.using(database).filter(pk__in=product_ids).update(has_been_in_stock=True)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0022_cd_wholesale_site_enabled_and_more"),
        ("warehouse", "0002_migrate_legacy_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="cd", name="has_been_in_stock",
            field=models.BooleanField(default=False, editable=False, verbose_name="Ранее был на физическом складе"),
        ),
        migrations.AddField(
            model_name="tech", name="has_been_in_stock",
            field=models.BooleanField(default=False, editable=False, verbose_name="Ранее был на физическом складе"),
        ),
        migrations.RunPython(initialize_stock_history, migrations.RunPython.noop),
    ]
