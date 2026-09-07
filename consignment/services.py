"""Атомарные операции передачи, возврата и продажи товара с реализации."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from cash.services import credit_sale_payment
from catalog.audit import field_change, record_product_changes, stock_change
from catalog.models import CD, ProductChangeEvent, Tech
from partners.models import SalesPlatform
from sales.models import Sale, SaleCDItem, SaleTechItem
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import (
    CDConsignmentStock,
    ConsignmentMovement,
    ConsignmentMovementItem,
    TechConsignmentStock,
)

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")


def _configuration(product_type):
    if product_type == "cd":
        return CD, CDConsignmentStock, CDWarehouseStock, SaleCDItem, "cd"
    if product_type == "tech":
        return Tech, TechConsignmentStock, TechWarehouseStock, SaleTechItem, "tech"
    raise ValidationError("Выберите существующий товар из списка.")


def _positive_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Количество должно быть целым числом.") from exc
    if quantity <= 0:
        raise ValidationError("Количество должно быть больше нуля.")
    return quantity


def _positive_receivable(value):
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную сумму к получению.") from exc
    if amount <= 0:
        raise ValidationError("Сумма к получению должна быть больше нуля.")
    return amount


def _normalise_transfer_lines(raw_lines):
    grouped = {}
    for raw in raw_lines:
        product_type = str(raw.get("product_type", "")).lower()
        if product_type not in {"cd", "tech"}:
            raise ValidationError("Выберите существующий товар из списка.")
        try:
            product_id = int(raw["product_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Заполните все поля товарных позиций.") from exc
        quantity = _positive_quantity(raw.get("quantity"))
        receivable = _positive_receivable(raw.get("receivable_per_unit"))
        key = (product_type, product_id)
        if key in grouped and grouped[key]["receivable_per_unit"] != receivable:
            raise ValidationError("У повторяющихся строк одного товара должна совпадать сумма к получению.")
        if key not in grouped:
            grouped[key] = {
                "product_type": product_type,
                "product_id": product_id,
                "quantity": 0,
                "receivable_per_unit": receivable,
            }
        grouped[key]["quantity"] += quantity
    if not grouped:
        raise ValidationError("Добавьте хотя бы один товар.")
    return list(grouped.values())


@transaction.atomic
def transfer_many_to_consignment(*, actor, warehouse_id, platform_id, lines):
    """Передаёт несколько товаров на одну площадку единым документом."""
    prepared = _normalise_transfer_lines(lines)
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
        platform = SalesPlatform.objects.get(pk=platform_id)
    except (Warehouse.DoesNotExist, SalesPlatform.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Выберите существующие склад и площадку.") from exc

    products = {}
    warehouse_stocks = {}
    consignment_stocks = {}
    for product_type in ("cd", "tech"):
        product_model, consignment_model, warehouse_stock_model, _, product_field = _configuration(product_type)
        ids = {line["product_id"] for line in prepared if line["product_type"] == product_type}
        products.update({
            (product_type, product.pk): product
            for product in product_model.objects.select_for_update().filter(pk__in=ids).order_by("pk")
        })
        warehouse_stocks.update({
            (product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in warehouse_stock_model.objects.select_for_update().filter(
                warehouse=warehouse, **{f"{product_field}_id__in": ids}
            ).order_by(product_field)
        })
        consignment_stocks.update({
            (product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in consignment_model.objects.select_for_update().filter(
                warehouse=warehouse, platform=platform, **{f"{product_field}_id__in": ids}
            ).order_by(product_field)
        })
    if len(products) != len(prepared):
        raise ValidationError("Выберите существующий товар из списка.")

    for line in prepared:
        key = (line["product_type"], line["product_id"])
        product = products[key]
        warehouse_stock = warehouse_stocks.get(key)
        if warehouse_stock is None or warehouse_stock.quantity < line["quantity"]:
            raise ValidationError(f"На складе «{warehouse.name}» недостаточно товара «{product.name}».")
        consignment_stock = consignment_stocks.get(key)
        if (
            consignment_stock is not None
            and consignment_stock.quantity > 0
            and consignment_stock.receivable_per_unit != line["receivable_per_unit"]
        ):
            raise ValidationError(
                f"Для товара «{product.name}» на этой площадке уже задана другая сумма к получению."
            )

    movement = ConsignmentMovement.objects.create(
        operation_type=ConsignmentMovement.OperationType.TRANSFER,
        platform=platform,
        warehouse=warehouse,
        created_by=actor,
    )
    movement_items = []
    for line in prepared:
        key = (line["product_type"], line["product_id"])
        product = products[key]
        warehouse_stock = warehouse_stocks[key]
        consignment_stock = consignment_stocks.get(key)
        _, consignment_model, _, _, product_field = _configuration(line["product_type"])
        if consignment_stock is None:
            consignment_stock = consignment_model(
                warehouse=warehouse,
                platform=platform,
                quantity=0,
                receivable_per_unit=line["receivable_per_unit"],
                **{product_field: product},
            )
        elif consignment_stock.quantity == 0:
            consignment_stock.receivable_per_unit = line["receivable_per_unit"]

        old_warehouse_quantity = warehouse_stock.quantity
        old_consignment_quantity = product.quantity_on_consignment
        warehouse_stock.quantity -= line["quantity"]
        product.quantity_on_consignment += line["quantity"]
        consignment_stock.quantity += line["quantity"]
        warehouse_stock.full_clean()
        product.full_clean(exclude=[
            field.name for field in product._meta.fields if field.name != "quantity_on_consignment"
        ])
        consignment_stock.full_clean()
        warehouse_stock.save(update_fields=("quantity",))
        product.save(update_fields=("quantity_on_consignment",))
        consignment_stock.save()
        movement_items.append(ConsignmentMovementItem(
            movement=movement,
            product_kind=line["product_type"],
            product_name_snapshot=product.name,
            product_sku_snapshot=product.sku,
            quantity=line["quantity"],
            receivable_per_unit=line["receivable_per_unit"],
            warehouse_quantity_before=old_warehouse_quantity,
            warehouse_quantity_after=warehouse_stock.quantity,
            consignment_quantity_before=old_consignment_quantity,
            consignment_quantity_after=product.quantity_on_consignment,
            **{product_field: product},
        ))
        record_product_changes(
            actor=actor,
            instance=product,
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.CONSIGNMENT,
            action_object_id=movement.pk,
            action_label=movement.action_label,
            changes=[
                stock_change(
                    warehouse=warehouse,
                    old_quantity=old_warehouse_quantity,
                    new_quantity=warehouse_stock.quantity,
                ),
                field_change(
                    field_name="quantity_on_consignment",
                    field_label="На реализации",
                    old_value=old_consignment_quantity,
                    new_value=product.quantity_on_consignment,
                ),
            ],
        )
    ConsignmentMovementItem.objects.bulk_create(movement_items)
    logger.info(
        "Товары переданы на реализацию: user_id=%s movement_id=%s platform_id=%s positions=%s units=%s",
        actor.pk, movement.pk, platform.pk, len(prepared), sum(line["quantity"] for line in prepared),
    )
    return movement


def transfer_to_consignment(
    *, actor, warehouse_id, platform_id, product_type, product_id, quantity,
    receivable_per_unit=None, reward_per_unit=None,
):
    """Совместимый однострочный вызов; интерфейс использует массовую операцию."""
    amount = receivable_per_unit if receivable_per_unit is not None else reward_per_unit
    transfer_many_to_consignment(
        actor=actor,
        warehouse_id=warehouse_id,
        platform_id=platform_id,
        lines=[{
            "product_type": product_type,
            "product_id": product_id,
            "quantity": quantity,
            "receivable_per_unit": amount,
        }],
    )
    _, stock_model, _, _, product_field = _configuration(product_type)
    return stock_model.objects.get(
        warehouse_id=warehouse_id,
        platform_id=platform_id,
        **{f"{product_field}_id": product_id},
    )


@transaction.atomic
def return_from_consignment(*, actor, warehouse_id, platform_id, product_type, product_id, quantity):
    quantity = _positive_quantity(quantity)
    product_model, consignment_model, warehouse_stock_model, _, product_field = _configuration(product_type)
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
        product = product_model.objects.select_for_update().get(pk=product_id)
        stock = consignment_model.objects.select_for_update().select_related("platform").get(
            warehouse=warehouse,
            platform_id=platform_id,
            **{f"{product_field}_id": product_id},
        )
    except (Warehouse.DoesNotExist, product_model.DoesNotExist, consignment_model.DoesNotExist) as exc:
        raise ValidationError("На выбранной площадке такого товара с этого склада нет.") from exc
    if stock.quantity < quantity:
        raise ValidationError(f"На выбранной площадке находится только {stock.quantity} единиц товара.")

    warehouse_stock = warehouse_stock_model.objects.select_for_update().filter(
        warehouse=warehouse, **{product_field: product}
    ).first()
    if warehouse_stock is None:
        warehouse_stock = warehouse_stock_model(warehouse=warehouse, **{product_field: product})
    old_warehouse_quantity = warehouse_stock.quantity
    old_consignment_quantity = product.quantity_on_consignment
    stock.quantity -= quantity
    product.quantity_on_consignment -= quantity
    warehouse_stock.quantity += quantity
    warehouse_stock.full_clean()
    product.full_clean(exclude=[
        field.name for field in product._meta.fields if field.name != "quantity_on_consignment"
    ])
    stock.full_clean()
    stock.save(update_fields=("quantity",))
    warehouse_stock.save()
    product.save(update_fields=("quantity_on_consignment",))
    movement = ConsignmentMovement.objects.create(
        operation_type=ConsignmentMovement.OperationType.RETURN,
        platform=stock.platform,
        warehouse=warehouse,
        created_by=actor,
    )
    ConsignmentMovementItem.objects.create(
        movement=movement,
        product_kind=product_type,
        product_name_snapshot=product.name,
        product_sku_snapshot=product.sku,
        quantity=quantity,
        receivable_per_unit=stock.receivable_per_unit,
        warehouse_quantity_before=old_warehouse_quantity,
        warehouse_quantity_after=warehouse_stock.quantity,
        consignment_quantity_before=old_consignment_quantity,
        consignment_quantity_after=product.quantity_on_consignment,
        **{product_field: product},
    )
    record_product_changes(
        actor=actor,
        instance=product,
        source=ProductChangeEvent.Source.CRM,
        action_kind=ProductChangeEvent.ActionKind.CONSIGNMENT,
        action_object_id=movement.pk,
        action_label=movement.action_label,
        changes=[
            stock_change(
                warehouse=warehouse,
                old_quantity=old_warehouse_quantity,
                new_quantity=warehouse_stock.quantity,
            ),
            field_change(
                field_name="quantity_on_consignment",
                field_label="На реализации",
                old_value=old_consignment_quantity,
                new_value=product.quantity_on_consignment,
            ),
        ],
    )
    logger.info(
        "Товар возвращён с реализации: user_id=%s movement_id=%s type=%s product_id=%s quantity=%s",
        actor.pk, movement.pk, product_type, product_id, quantity,
    )
    return stock


@transaction.atomic
def record_consignment_sale(*, actor, product_type, stock_id, quantity, payment_method):
    """Фиксирует продажу с реализации без повторного списания со склада."""
    quantity = _positive_quantity(quantity)
    allowed_payment_methods = {Sale.PaymentMethod.CASH, Sale.PaymentMethod.BANK_ACCOUNT}
    if payment_method not in allowed_payment_methods:
        raise ValidationError("Выберите наличные или банковский счёт.")
    product_model, stock_model, _, sale_item_model, product_field = _configuration(product_type)
    try:
        stock = stock_model.objects.select_for_update().select_related(
            "warehouse", "platform", product_field
        ).get(pk=stock_id)
    except stock_model.DoesNotExist as exc:
        raise ValidationError("Остаток товара на реализации не найден.") from exc
    product = product_model.objects.select_for_update().get(pk=getattr(stock, f"{product_field}_id"))
    if stock.quantity < quantity:
        raise ValidationError(f"На реализации осталось только {stock.quantity} единиц товара.")
    unit_price = stock.receivable_per_unit.quantize(CENT, rounding=ROUND_HALF_UP)
    if unit_price <= 0:
        raise ValidationError("Для товара не задана сумма к получению при продаже.")
    total = (unit_price * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    now = timezone.now()
    sale = Sale.objects.create(
        warehouse=stock.warehouse,
        consignment_platform=stock.platform,
        price_type=Sale.PriceType.CONSIGNMENT,
        sale_type=Sale.SaleType.CONSIGNMENT,
        payment_method=payment_method,
        order_status=Sale.OrderStatus.DELIVERED,
        payment_status=Sale.PaymentStatus.PAID,
        completed_at=now,
        total_amount=total,
        created_by=actor,
    )
    sale.visible_id = f"SALE-{sale.pk:06d}"
    sale.save(update_fields=("visible_id",))
    sale_item_model.objects.create(
        sale=sale,
        quantity=quantity,
        unit_price=unit_price,
        line_total=total,
        product_name_snapshot=product.name,
        article_snapshot=product.sku,
        **{product_field: product},
    )

    old_stock_quantity = stock.quantity
    old_consignment_quantity = product.quantity_on_consignment
    stock.quantity -= quantity
    product.quantity_on_consignment -= quantity
    stock.full_clean()
    product.full_clean(exclude=[
        field.name for field in product._meta.fields if field.name != "quantity_on_consignment"
    ])
    stock.save(update_fields=("quantity",))
    product.save(update_fields=("quantity_on_consignment",))
    record_product_changes(
        actor=actor,
        instance=product,
        source=ProductChangeEvent.Source.CRM,
        action_kind=ProductChangeEvent.ActionKind.SALE,
        action_object_id=sale.pk,
        action_label=f"Продажа {sale.visible_id}",
        changes=[
            field_change(
                field_name=f"consignment_stock_{product_type}_{stock.pk}",
                field_label=f"На реализации: {stock.platform.name} ({stock.warehouse.name})",
                old_value=old_stock_quantity,
                new_value=stock.quantity,
            ),
            field_change(
                field_name="quantity_on_consignment",
                field_label="Всего на реализации",
                old_value=old_consignment_quantity,
                new_value=product.quantity_on_consignment,
            ),
        ],
    )
    if payment_method == Sale.PaymentMethod.CASH:
        credit_sale_payment(sale=sale, actor=actor)
    logger.info(
        "Товар реализован: user_id=%s sale_id=%s platform_id=%s type=%s product_id=%s quantity=%s total=%s",
        actor.pk, sale.pk, stock.platform_id, product_type, product.pk, quantity, total,
    )
    return sale
