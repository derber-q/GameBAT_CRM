"""Атомарные операции с межскладскими перемещениями."""
import logging
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.audit import record_product_changes, stock_change
from catalog.models import CD, ProductChangeEvent, Tech
from .storage_services import clear_storage_locations_if_zero
from .models import (
    CDWarehouseStock,
    CDWarehouseTransferItem,
    TechWarehouseStock,
    TechWarehouseTransferItem,
    Warehouse,
    WarehouseTransfer,
)

logger = logging.getLogger("gamebat.business")


def stock_configuration(product_type):
    if product_type == "cd":
        return CD, CDWarehouseStock, "cd"
    if product_type == "tech":
        return Tech, TechWarehouseStock, "tech"
    raise ValidationError("Выберите существующий товар из списка.")


def normalise_product_lines(raw_lines):
    """Проверяет строки и объединяет повторы одного товара."""
    grouped = defaultdict(int)
    for raw in raw_lines:
        product_type = str(raw.get("product_type", "")).lower()
        if product_type not in {"cd", "tech"}:
            raise ValidationError("Выберите существующий товар из списка.")
        try:
            product_id = int(raw["product_id"])
            quantity = int(raw["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Заполните все поля товарной позиции.") from exc
        if quantity <= 0:
            raise ValidationError("Количество должно быть больше нуля.")
        grouped[(product_type, product_id)] += quantity
    if not grouped:
        raise ValidationError("Добавьте хотя бы один товар.")
    return [
        {"product_type": product_type, "product_id": product_id, "quantity": quantity}
        for (product_type, product_id), quantity in grouped.items()
    ]


@transaction.atomic
def create_transfer(*, actor, source_warehouse_id, destination_warehouse_id, lines):
    """Списывает товар у отправителя и фиксирует неизменяемый состав перемещения."""
    prepared = normalise_product_lines(lines)
    try:
        source_id = int(source_warehouse_id)
        destination_id = int(destination_warehouse_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Выберите склады отправления и назначения.") from exc
    if source_id == destination_id:
        raise ValidationError("Склад отправления и склад назначения должны различаться.")

    warehouses = {
        item.pk: item
        for item in Warehouse.objects.select_for_update().filter(pk__in=(source_id, destination_id)).order_by("pk")
    }
    if len(warehouses) != 2:
        raise ValidationError("Выберите существующие склады.")

    stocks = {}
    products = {}
    for product_type in ("cd", "tech"):
        product_model, stock_model, product_field = stock_configuration(product_type)
        ids = {line["product_id"] for line in prepared if line["product_type"] == product_type}
        products.update({
            (product_type, product.pk): product
            for product in product_model.objects.filter(pk__in=ids).order_by("pk")
        })
        stocks.update({
            (product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in stock_model.objects.select_for_update().filter(
                warehouse_id=source_id, **{f"{product_field}_id__in": ids}
            ).order_by(product_field)
        })
    if len(products) != len(prepared):
        raise ValidationError("Выберите существующий товар из списка.")

    for line in prepared:
        key = (line["product_type"], line["product_id"])
        stock = stocks.get(key)
        if stock is None or stock.quantity < line["quantity"]:
            product = products[key]
            raise ValidationError(f"На складе «{warehouses[source_id].name}» недостаточно товара «{product.name}».")

    transfer = WarehouseTransfer.objects.create(
        source_warehouse=warehouses[source_id], destination_warehouse=warehouses[destination_id], created_by=actor
    )
    cd_items, tech_items = [], []
    for line in prepared:
        key = (line["product_type"], line["product_id"])
        stock = stocks[key]
        old_quantity = stock.quantity
        stock.quantity -= line["quantity"]
        stock.full_clean()
        stock.save(update_fields=("quantity",))
        record_product_changes(
            actor=actor,
            instance=products[key],
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.WAREHOUSE_TRANSFER,
            action_object_id=transfer.pk,
            action_label=f"Перемещение №{transfer.pk}",
            changes=[stock_change(
                warehouse=warehouses[source_id],
                old_quantity=old_quantity,
                new_quantity=stock.quantity,
            )],
        )
        clear_storage_locations_if_zero(
            stock=stock,
            actor=actor,
            action_kind=ProductChangeEvent.ActionKind.WAREHOUSE_TRANSFER,
            action_object_id=transfer.pk,
            action_label=f"Перемещение №{transfer.pk}",
        )
        if line["product_type"] == "cd":
            cd_items.append(CDWarehouseTransferItem(transfer=transfer, cd=products[key], quantity=line["quantity"]))
        else:
            tech_items.append(
                TechWarehouseTransferItem(transfer=transfer, tech=products[key], quantity=line["quantity"])
            )
    CDWarehouseTransferItem.objects.bulk_create(cd_items)
    TechWarehouseTransferItem.objects.bulk_create(tech_items)
    logger.info(
        "Перемещение создано: user_id=%s transfer_id=%s source_id=%s destination_id=%s units=%s",
        actor.pk, transfer.pk, source_id, destination_id, sum(line["quantity"] for line in prepared),
    )
    return transfer


@transaction.atomic
def advance_transfer_status(*, actor, transfer_id, next_status):
    """Выполняет только следующий переход; при приёмке зачисляет товар получателю."""
    transfer = WarehouseTransfer.objects.select_for_update().select_related(
        "source_warehouse", "destination_warehouse"
    ).get(pk=transfer_id)
    transitions = {
        WarehouseTransfer.Status.CREATED: WarehouseTransfer.Status.ASSEMBLED,
        WarehouseTransfer.Status.ASSEMBLED: WarehouseTransfer.Status.SHIPPED,
        WarehouseTransfer.Status.SHIPPED: WarehouseTransfer.Status.ACCEPTED,
    }
    expected = transitions.get(transfer.status)
    if expected is None or next_status != expected:
        raise ValidationError("Этот переход статуса недопустим.")

    now = timezone.now()
    update_fields = ["status", "updated_at"]
    transfer.status = next_status
    if next_status == WarehouseTransfer.Status.ASSEMBLED:
        transfer.assembled_at = now
        transfer.assembled_by = actor
        update_fields.extend(("assembled_at", "assembled_by"))
    elif next_status == WarehouseTransfer.Status.SHIPPED:
        transfer.shipped_at = now
        transfer.shipped_by = actor
        update_fields.extend(("shipped_at", "shipped_by"))
    else:
        # Блокировка склада-получателя сериализует создание отсутствующих stock rows.
        Warehouse.objects.select_for_update().get(pk=transfer.destination_warehouse_id)
        for product_type, stock_model, product_field, items in (
            ("cd", CDWarehouseStock, "cd", transfer.cd_items.all()),
            ("tech", TechWarehouseStock, "tech", transfer.tech_items.all()),
        ):
            item_list = list(items)
            ids = [getattr(item, f"{product_field}_id") for item in item_list]
            existing = {
                getattr(stock, f"{product_field}_id"): stock
                for stock in stock_model.objects.select_for_update().filter(
                    warehouse_id=transfer.destination_warehouse_id,
                    **{f"{product_field}_id__in": ids},
                )
            }
            for item in item_list:
                product_id = getattr(item, f"{product_field}_id")
                stock = existing.get(product_id)
                if stock is None:
                    stock = stock_model(
                        warehouse_id=transfer.destination_warehouse_id,
                        **{f"{product_field}_id": product_id},
                    )
                old_quantity = stock.quantity
                stock.quantity += item.quantity
                stock.full_clean()
                stock.save()
                record_product_changes(
                    actor=actor,
                    instance=getattr(item, product_field),
                    source=ProductChangeEvent.Source.CRM,
                    action_kind=ProductChangeEvent.ActionKind.WAREHOUSE_TRANSFER,
                    action_object_id=transfer.pk,
                    action_label=f"Перемещение №{transfer.pk}",
                    changes=[stock_change(
                        warehouse=transfer.destination_warehouse,
                        old_quantity=old_quantity,
                        new_quantity=stock.quantity,
                    )],
                )
        transfer.accepted_at = now
        transfer.accepted_by = actor
        update_fields.extend(("accepted_at", "accepted_by"))
    transfer.save(update_fields=update_fields)
    logger.info(
        "Статус перемещения изменён: user_id=%s transfer_id=%s status=%s",
        actor.pk, transfer.pk, next_status,
    )
    return transfer
