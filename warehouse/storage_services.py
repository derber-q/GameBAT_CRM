"""Атомарные операции с физическими местами хранения товарных остатков."""
import logging
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from catalog.audit import field_change, record_product_changes
from catalog.models import CD, ProductChangeEvent, Tech

from .models import (
    CDWarehouseStorageAssignment,
    CDWarehouseStock,
    TechWarehouseStock,
    TechWarehouseStorageAssignment,
    Warehouse,
    WarehouseStorageLocation,
)
from .storage_locations import (
    normalize_location_autocomplete_token,
    parse_storage_location_list,
    parse_storage_location_query,
)


logger = logging.getLogger("gamebat.business")


@dataclass(frozen=True)
class StorageLocationUpdateResult:
    value: str
    changed: bool


def assignment_configuration(product_type):
    if product_type == "cd":
        return CDWarehouseStorageAssignment
    if product_type == "tech":
        return TechWarehouseStorageAssignment
    raise ValidationError("Выберите существующий товар.")


def storage_stock_configuration(product_type):
    if product_type == "cd":
        return CD, CDWarehouseStock, "cd"
    if product_type == "tech":
        return Tech, TechWarehouseStock, "tech"
    raise ValidationError("Выберите существующий товар.")


def storage_locations_value(assignments):
    return ", ".join(assignment.location.canonical_value for assignment in assignments)


def storage_locations_for_stock(stock):
    return storage_locations_value(stock.storage_assignments.all())


def storage_location_product_ids(*, warehouse, raw_query, include_cd=True, include_tech=True):
    """Возвращает product IDs по структурному GET-фильтру, без substring-сравнений."""
    query = parse_storage_location_query(raw_query)
    if query is None:
        return None, None
    locations = WarehouseStorageLocation.objects.filter(warehouse=warehouse, room=query.room)
    if query.rack is not None:
        locations = locations.filter(rack=query.rack)
    if query.shelf is not None:
        locations = locations.filter(shelf=query.shelf)
    location_ids = [
        location.pk
        for location in locations.only("id", "columns")
        if not query.columns or set(query.columns).issubset(set(location.columns))
    ]
    cd_ids = set()
    tech_ids = set()
    if include_cd:
        cd_ids = set(CDWarehouseStorageAssignment.objects.filter(
            location_id__in=location_ids, stock__warehouse=warehouse,
        ).values_list("stock__cd_id", flat=True))
    if include_tech:
        tech_ids = set(TechWarehouseStorageAssignment.objects.filter(
            location_id__in=location_ids, stock__warehouse=warehouse,
        ).values_list("stock__tech_id", flat=True))
    return cd_ids, tech_ids


def autocomplete_storage_locations(*, warehouse, raw_query, include_cd=True, include_tech=True, limit=20):
    """Подсказывает только реально используемые locations разрешённых типов текущего склада."""
    token = normalize_location_autocomplete_token(raw_query)
    if not token:
        return []
    relation_filter = Q(pk__in=[])
    if include_cd:
        relation_filter |= Q(cd_assignments__stock__warehouse=warehouse)
    if include_tech:
        relation_filter |= Q(tech_assignments__stock__warehouse=warehouse)
    locations = list(
        WarehouseStorageLocation.objects.filter(warehouse=warehouse).filter(relation_filter)
        .distinct().order_by("room", "rack", "shelf", "canonical_value")
    )
    try:
        query = parse_storage_location_query(token)
    except ValidationError:
        query = None

    def matches(location):
        if query is None:
            return location.canonical_value.startswith(token)
        return (
            location.room == query.room
            and (query.rack is None or location.rack == query.rack)
            and (query.shelf is None or location.shelf == query.shelf)
            and (not query.columns or set(query.columns).issubset(set(location.columns)))
        )

    return [location.canonical_value for location in locations if matches(location)][:limit]


def _location_change(*, warehouse, old_value, new_value):
    return field_change(
        field_name=f"warehouse_storage_locations_{warehouse.pk}",
        field_label=f"Места хранения: {warehouse.name}",
        old_value=old_value,
        new_value=new_value,
    )


@transaction.atomic
def update_storage_locations(
    *, actor, warehouse_id, product_type, product_id, raw_value,
    source=ProductChangeEvent.Source.CRM,
):
    """Заменяет весь упорядоченный список locations для одного WarehouseStock."""
    parsed = parse_storage_location_list(raw_value)
    warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    product_model, stock_model, product_field = storage_stock_configuration(product_type)
    product = product_model.objects.select_for_update().get(pk=product_id)
    stock = stock_model.objects.select_for_update().filter(
        warehouse=warehouse, **{f"{product_field}_id": product.pk}
    ).first()
    if stock is None or stock.quantity <= 0:
        raise ValidationError("Место хранения можно указать только для товара с положительным остатком на складе.")

    assignment_model = assignment_configuration(product_type)
    old_assignments = list(
        assignment_model.objects.select_for_update().select_related("location")
        .filter(stock=stock).order_by("position", "id")
    )
    old_value = storage_locations_value(old_assignments)
    new_value = ", ".join(item.canonical for item in parsed)
    if old_value == new_value:
        return StorageLocationUpdateResult(value=old_value, changed=False)

    locations = []
    for item in parsed:
        location, _ = WarehouseStorageLocation.objects.get_or_create(
            warehouse=warehouse,
            canonical_value=item.canonical,
            defaults={
                "room": item.room,
                "rack": item.rack,
                "shelf": item.shelf,
                "columns": list(item.columns),
            },
        )
        locations.append(location)

    assignment_model.objects.filter(stock=stock).delete()
    assignment_model.objects.bulk_create([
        assignment_model(stock=stock, location=location, position=position)
        for position, location in enumerate(locations)
    ])
    record_product_changes(
        actor=actor,
        instance=product,
        source=source,
        changes=[_location_change(
            warehouse=warehouse, old_value=old_value, new_value=new_value,
        )],
    )
    logger.info(
        "Места хранения изменены: user_id=%s warehouse_id=%s type=%s product_id=%s old=%s new=%s",
        actor.pk, warehouse.pk, product_type, product.pk, old_value, new_value,
    )
    return StorageLocationUpdateResult(value=new_value, changed=True)


def clear_storage_locations_if_zero(
    *, stock, actor, source=ProductChangeEvent.Source.CRM,
    action_kind="", action_object_id=None, action_label=""
):
    """Удаляет assignments при нулевом остатке внутри транзакции исходной операции."""
    if stock.quantity != 0 or not stock.pk:
        return False
    assignment_model = assignment_configuration("cd" if hasattr(stock, "cd_id") else "tech")
    assignments = list(
        assignment_model.objects.select_for_update().select_related("location")
        .filter(stock=stock).order_by("position", "id")
    )
    if not assignments:
        return False
    old_value = storage_locations_value(assignments)
    assignment_model.objects.filter(pk__in=[assignment.pk for assignment in assignments]).delete()
    product = stock.cd if hasattr(stock, "cd_id") else stock.tech
    record_product_changes(
        actor=actor,
        instance=product,
        source=source,
        action_kind=action_kind,
        action_object_id=action_object_id,
        action_label=action_label,
        changes=[_location_change(
            warehouse=stock.warehouse,
            old_value=old_value,
            new_value="",
        )],
    )
    logger.info(
        "Места хранения очищены автоматически: остаток стал 0: user_id=%s warehouse_id=%s stock_id=%s",
        getattr(actor, "pk", None), stock.warehouse_id, stock.pk,
    )
    return True
