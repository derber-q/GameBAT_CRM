"""Места хранения для сборки незавершённой продажи без изменения складских данных."""

from django.db.models import OuterRef, Prefetch, Q, Subquery

from catalog.models import ProductChangeEvent, ProductFieldChange
from warehouse.models import (
    CDWarehouseStock,
    CDWarehouseStorageAssignment,
    TechWarehouseStock,
    TechWarehouseStorageAssignment,
)
from warehouse.storage_services import storage_locations_for_stock

from .models import Sale


def sale_storage_locations(sale):
    """Возвращает адреса склада продажи; очищенные при продаже адреса помечает историческими."""
    if sale.is_cancelled or sale.is_completed or sale.sale_type == Sale.SaleType.CONSIGNMENT:
        return {}

    products = {
        "cd": {item.cd_id for item in sale.cd_items.all()},
        "tech": {item.tech_id for item in sale.tech_items.all()},
    }
    locations = {}
    cleared_products = {"cd": set(), "tech": set()}
    last_stock_changes = {}
    for kind, stock_model, assignment_model in (
        ("cd", CDWarehouseStock, CDWarehouseStorageAssignment),
        ("tech", TechWarehouseStock, TechWarehouseStorageAssignment),
    ):
        if not products[kind]:
            continue
        last_stock_change = ProductFieldChange.objects.filter(
            field_name=f"warehouse_stock_{sale.warehouse_id}",
            **{f"event__{kind}_id": OuterRef(f"{kind}_id")},
        ).order_by("-event__created_at", "-event_id", "-pk").values("event__created_at")[:1]
        stocks = stock_model.objects.filter(
            warehouse_id=sale.warehouse_id, **{f"{kind}_id__in": products[kind]},
        ).annotate(last_stock_change_at=Subquery(last_stock_change)).prefetch_related(Prefetch(
            "storage_assignments",
            queryset=assignment_model.objects.select_related("location").order_by("position", "id"),
        ))
        for stock in stocks:
            product_id = getattr(stock, f"{kind}_id")
            value = storage_locations_for_stock(stock)
            if value:
                locations[(kind, product_id)] = {"storage_locations": value, "storage_location_is_previous": False}
            elif stock.quantity == 0:
                cleared_products[kind].add(product_id)
                last_stock_changes[(kind, product_id)] = stock.last_stock_change_at

    if not any(cleared_products.values()):
        return locations

    # Сначала читаем последнее изменение, включая ручные очистки и перемещения:
    # более старый адрес не подставляется вместо явно удалённого или перенесённого.
    changes = ProductFieldChange.objects.filter(
        Q(event__cd_id__in=cleared_products["cd"]) | Q(event__tech_id__in=cleared_products["tech"]),
        field_name=f"warehouse_storage_locations_{sale.warehouse_id}",
    ).order_by("-event__created_at", "-event_id", "-pk").values(
        "event__product_kind", "event__cd_id", "event__tech_id", "event__action_kind",
        "event__created_at", "old_value", "new_value",
    )
    seen = set()
    required = sum(len(ids) for ids in cleared_products.values())
    for change in changes.iterator():
        kind = change["event__product_kind"]
        key = (kind, change[f"event__{kind}_id"])
        if key in seen:
            continue
        seen.add(key)
        # После поступления и нового списания без адреса прежнее размещение уже неизвестно.
        latest_stock_change = last_stock_changes.get(key)
        if (
            change["event__action_kind"] == ProductChangeEvent.ActionKind.SALE
            and change["event__created_at"] >= sale.created_at
            and (latest_stock_change is None or change["event__created_at"] >= latest_stock_change)
            and change["old_value"] and not change["new_value"]
        ):
            locations[key] = {
                "storage_locations": change["old_value"],
                "storage_location_is_previous": True,
            }
        if len(seen) == required:
            break
    return locations
