"""Общие для склада циклы проверки; физические остатки здесь только читаются."""
from itertools import groupby
from functools import wraps
from time import sleep

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import Prefetch
from django.utils import timezone

from .models import (
    Warehouse, WarehouseRevision, WarehouseRevisionItem,
    CDWarehouseStock, TechWarehouseStock,
    CDWarehouseStorageAssignment, TechWarehouseStorageAssignment,
)
from .storage_locations import parse_storage_location
from .storage_services import storage_locations_for_stock


class RevisionConflict(ValidationError):
    pass


def _retry_busy(operation):
    """Повторяет целую короткую транзакцию при конкуренции записей SQLite."""
    @wraps(operation)
    def wrapped(*args, **kwargs):
        for attempt in range(5):
            try:
                return operation(*args, **kwargs)
            except OperationalError as exc:
                if connection.vendor != "sqlite" or "locked" not in str(exc).lower() or connection.in_atomic_block:
                    raise
                if attempt == 4:
                    raise RevisionConflict("Склад сейчас обновляется. Повторите действие через несколько секунд.") from exc
                sleep(0.05 * (attempt + 1))
    return wrapped


def allowed_kinds(user):
    full = user.is_superuser or user.has_perm("warehouse.view_warehouse_stock")
    return tuple(kind for kind in ("cd", "tech") if full or user.has_perm(f"catalog.view_{kind}"))


@_retry_busy
@transaction.atomic
def start_revision(*, warehouse_id, actor, expected_revision_id):
    if not (actor.is_superuser or actor.has_perm("warehouse.view_warehouse_stock")):
        raise PermissionDenied("Для начала общей ревизии нужен доступ ко всем остаткам склада.")
    warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    current = WarehouseRevision.objects.filter(warehouse=warehouse, is_active=True).first()
    if (current.pk if current else None) != expected_revision_id:
        raise RevisionConflict("Другой сотрудник уже начал новую ревизию. Обновите страницу.")
    if current:
        current.is_active = False
        current.closed_at = timezone.now()
        current.save(update_fields=("is_active", "closed_at"))
    return WarehouseRevision.objects.create(warehouse=warehouse, started_by=actor)


@_retry_busy
@transaction.atomic
def set_checked(*, warehouse_id, revision_id, kind, product_id, checked, actor):
    if kind not in allowed_kinds(actor):
        raise PermissionDenied("Нет доступа к этому типу товаров.")
    # SQLite использует IMMEDIATE из настроек проекта; для БД с блокировками
    # строк общий порядок Warehouse → Stock сериализует начало цикла и отметки.
    Warehouse.objects.select_for_update().get(pk=warehouse_id)
    revision = WarehouseRevision.objects.filter(warehouse_id=warehouse_id, is_active=True).first()
    if revision_id is None and revision is None:
        if not (actor.is_superuser or actor.has_perm("warehouse.view_warehouse_stock")):
            raise PermissionDenied("Для начала ревизии нужен доступ ко всем остаткам склада.")
        if WarehouseRevision.objects.filter(warehouse_id=warehouse_id).exists():
            raise RevisionConflict("Предыдущая ревизия закрыта. Начните новый цикл кнопкой «Новая ревизия».")
        revision = WarehouseRevision.objects.create(warehouse_id=warehouse_id, started_by=actor)
    elif revision is None or revision.pk != revision_id:
        raise RevisionConflict("Эта ревизия уже закрыта. Обновите страницу для продолжения.")
    model = CDWarehouseStock if kind == "cd" else TechWarehouseStock
    stock = model.objects.select_for_update().filter(warehouse_id=warehouse_id, **{f"{kind}_id": product_id}).first()
    if stock is None or stock.quantity <= 0:
        raise RevisionConflict("Товара больше нет на этом складе. Обновите страницу.")
    item, _ = WarehouseRevisionItem.objects.get_or_create(revision=revision, **{f"{kind}_id": product_id})
    item.checked = checked
    item.checked_at = timezone.now() if checked else None
    item.checked_by = actor if checked else None
    item.invalidated_at = None
    item.save(update_fields=("checked", "checked_at", "checked_by", "invalidated_at"))
    return item


def revision_rows(*, warehouse, revision, kinds):
    states = {}
    if revision:
        states = {( "cd" if item.cd_id else "tech", item.cd_id or item.tech_id): item
                  for item in revision.items.all()}
    rows = []
    for kind, model, assignment, relation in (
        ("cd", CDWarehouseStock, CDWarehouseStorageAssignment, "platform"),
        ("tech", TechWarehouseStock, TechWarehouseStorageAssignment, "product_type"),
    ):
        if kind not in kinds:
            continue
        stocks = model.objects.filter(warehouse=warehouse, quantity__gt=0).select_related(
            f"{kind}__{relation}"
        ).prefetch_related(Prefetch("storage_assignments", queryset=assignment.objects.select_related("location").order_by("position", "id")))
        for stock in stocks:
            product = getattr(stock, kind)
            assignments = list(stock.storage_assignments.all())
            first = assignments[0].location.canonical_value if assignments else ""
            location = parse_storage_location(first) if first else None
            state = states.get((kind, product.pk))
            rows.append({
                "kind": kind, "product": product, "quantity": stock.quantity,
                "locations": storage_locations_for_stock(stock), "first_location": first,
                "location_key": (0, location.room, location.rack, location.shelf, location.columns) if location else (1, "", 0, 0, ()),
                "group": getattr(product, relation).name,
                "group_id": getattr(product, f"{relation}_id"),
                "checked": bool(state and state.checked and state.invalidated_at is None),
            })
    return rows


def grouped_rows(rows, mode):
    if mode == "locations":
        ordered = sorted(rows, key=lambda row: (row["location_key"], row["product"].name.casefold(), row["kind"], row["product"].pk))
        key = lambda row: row["first_location"] or "Без места хранения"
    else:
        ordered = sorted(rows, key=lambda row: (row["kind"], row["group"].casefold(), row["group_id"], row["product"].name.casefold(), row["product"].pk))
        key = lambda row: (row["kind"], row["group_id"], row["group"])
    return [{"title": group if mode == "locations" else f"{group[0].upper()} · {group[2]}", "rows": list(items)}
            for group, items in groupby(ordered, key=key)]


def progress(rows):
    total = len(rows)
    checked = sum(row["checked"] for row in rows)
    return {"checked": checked, "total": total, "percent": round(checked * 100 / total, 1) if total else 0}
