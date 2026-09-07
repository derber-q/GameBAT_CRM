"""Неизменяемые снимки изменений карточек CD и Tech."""
from decimal import Decimal

from .models import CD, ProductChangeEvent, ProductFieldChange, Tech


def snapshot_value(instance, field_name):
    field = instance._meta.get_field(field_name)
    value = getattr(instance, field_name)
    if value in (None, ""):
        return ""
    if field.is_relation:
        return str(value)
    if isinstance(value, Decimal):
        return f"{value:.{field.decimal_places}f}"
    return str(value)


def product_snapshot(instance, field_names):
    return {field_name: snapshot_value(instance, field_name) for field_name in field_names}


def changed_snapshots(instance, before, field_names):
    changes = []
    for field_name in field_names:
        old_value = before[field_name]
        new_value = snapshot_value(instance, field_name)
        if old_value != new_value:
            changes.append({
                "field_name": field_name,
                "field_label": str(instance._meta.get_field(field_name).verbose_name),
                "old_value": old_value,
                "new_value": new_value,
            })
    return changes


def stock_change(*, warehouse, old_quantity, new_quantity):
    return {
        "field_name": f"warehouse_stock_{warehouse.pk}",
        "field_label": f"Остаток: {warehouse.name}",
        "old_value": str(old_quantity),
        "new_value": str(new_quantity),
    }


def field_change(*, field_name, field_label, old_value, new_value):
    return {
        "field_name": field_name,
        "field_label": field_label,
        "old_value": str(old_value),
        "new_value": str(new_value),
    }


def record_product_changes(
    *, actor, instance, changes, source, action_kind="", action_object_id=None, action_label=""
):
    """Записывает одну пользовательскую операцию и её изменения в текущей транзакции."""
    if not changes:
        return None
    if isinstance(instance, CD):
        product_kind = ProductChangeEvent.ProductKind.CD
        product_reference = {"cd": instance}
    elif isinstance(instance, Tech):
        product_kind = ProductChangeEvent.ProductKind.TECH
        product_reference = {"tech": instance}
    else:
        raise TypeError("История поддерживается только для CD и Tech.")
    event = ProductChangeEvent.objects.create(
        actor=actor,
        source=source,
        product_kind=product_kind,
        action_kind=action_kind,
        action_object_id=action_object_id,
        action_label=action_label,
        **product_reference,
    )
    ProductFieldChange.objects.bulk_create([
        ProductFieldChange(event=event, **change) for change in changes
    ])
    return event
