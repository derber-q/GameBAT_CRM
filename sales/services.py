"""Атомарные продажи, статусы, оплаты и изменение неоплаченной постоплаты."""
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from cash.services import credit_sale_payment
from catalog.audit import record_product_changes, stock_change
from catalog.models import CD, ProductChangeEvent, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.services import normalise_product_lines
from .models import Sale, SaleCDItem, SaleTechItem

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")


def _configuration(product_type):
    if product_type == "cd":
        return CD, CDWarehouseStock, SaleCDItem, "cd"
    if product_type == "tech":
        return Tech, TechWarehouseStock, SaleTechItem, "tech"
    raise ValidationError("Выберите существующий товар из списка.")


def _validate_choice(value, choices, message):
    if value not in choices.values:
        raise ValidationError(message)
    return value


def _locked_inventory(warehouse_id, lines):
    """Блокирует товары и локальные остатки; product lock синхронизирует продажи с пересчётом cost."""
    products, stocks = {}, {}
    for product_type in ("cd", "tech"):
        product_model, stock_model, _, product_field = _configuration(product_type)
        ids = {line["product_id"] for line in lines if line["product_type"] == product_type}
        products.update({
            (product_type, product.pk): product
            for product in product_model.objects.select_for_update().filter(pk__in=ids).order_by("pk")
        })
        stocks.update({
            (product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in stock_model.objects.select_for_update().filter(
                warehouse_id=warehouse_id, **{f"{product_field}_id__in": ids}
            ).order_by(product_field)
        })
    if len(products) != len(lines):
        raise ValidationError("Выберите существующий товар из списка.")
    return products, stocks


def _selected_price(product, price_type):
    field = {
        Sale.PriceType.RETAIL: "retail_price",
        Sale.PriceType.WHOLESALE: "wholesale_price",
        Sale.PriceType.YANDEX_MARKET: "yandex_market_price",
    }[price_type]
    price = getattr(product, field)
    if price is None:
        raise ValidationError(f"Для товара «{product.name}» не задана выбранная цена продажи.")
    return price.quantize(CENT, rounding=ROUND_HALF_UP)


def _complete_if_ready(sale):
    if sale.order_status == Sale.OrderStatus.DELIVERED and sale.payment_status == Sale.PaymentStatus.PAID:
        sale.completed_at = sale.completed_at or timezone.now()
        return True
    return False


@transaction.atomic
def create_sale(*, actor, warehouse_id, price_type, sale_type, payment_method, lines):
    """Списывает локальный stock и для наличной продажи в той же транзакции проводит кассу."""
    prepared = normalise_product_lines(lines)
    _validate_choice(price_type, Sale.PriceType, "Выберите тип цены.")
    _validate_choice(sale_type, Sale.SaleType, "Выберите тип продажи.")
    _validate_choice(payment_method, Sale.PaymentMethod, "Выберите способ оплаты.")
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    products, stocks = _locked_inventory(warehouse.pk, prepared)
    priced_lines = []
    total = Decimal("0")
    for line in prepared:
        key = (line["product_type"], line["product_id"])
        product = products[key]
        stock = stocks.get(key)
        if stock is None or stock.quantity < line["quantity"]:
            raise ValidationError(f"На выбранном складе недостаточно товара «{product.name}».")
        price = _selected_price(product, price_type)
        line_total = (price * line["quantity"]).quantize(CENT, rounding=ROUND_HALF_UP)
        priced_lines.append((line, product, stock, price, line_total))
        total += line_total

    immediate_cash = payment_method == Sale.PaymentMethod.CASH
    sale = Sale.objects.create(
        warehouse=warehouse,
        price_type=price_type,
        sale_type=sale_type,
        payment_method=payment_method,
        order_status=Sale.OrderStatus.DELIVERED if immediate_cash else Sale.OrderStatus.CREATED,
        payment_status=Sale.PaymentStatus.PAID if immediate_cash else Sale.PaymentStatus.UNPAID,
        completed_at=timezone.now() if immediate_cash else None,
        total_amount=total,
        created_by=actor,
    )
    sale.visible_id = f"SALE-{sale.pk:06d}"
    sale.save(update_fields=("visible_id",))

    cd_items, tech_items = [], []
    for line, product, stock, price, line_total in priced_lines:
        old_quantity = stock.quantity
        stock.quantity -= line["quantity"]
        stock.full_clean()
        stock.save(update_fields=("quantity",))
        record_product_changes(
            actor=actor,
            instance=product,
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Продажа {sale.visible_id}",
            changes=[stock_change(
                warehouse=warehouse,
                old_quantity=old_quantity,
                new_quantity=stock.quantity,
            )],
        )
        values = dict(
            sale=sale, quantity=line["quantity"], unit_price=price, line_total=line_total,
            product_name_snapshot=product.name, article_snapshot=product.sku,
        )
        if line["product_type"] == "cd":
            cd_items.append(SaleCDItem(cd=product, **values))
        else:
            tech_items.append(SaleTechItem(tech=product, **values))
    SaleCDItem.objects.bulk_create(cd_items)
    SaleTechItem.objects.bulk_create(tech_items)
    if immediate_cash:
        credit_sale_payment(sale=sale, actor=actor)
    logger.info(
        "Продажа создана: user_id=%s sale_id=%s warehouse_id=%s total=%s payment=%s",
        actor.pk, sale.pk, warehouse.pk, total, payment_method,
    )
    return sale


@transaction.atomic
def advance_order_status(*, actor, sale_id, next_status):
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    transitions = {
        Sale.OrderStatus.CREATED: Sale.OrderStatus.ASSEMBLED,
        Sale.OrderStatus.ASSEMBLED: Sale.OrderStatus.SHIPPED,
        Sale.OrderStatus.SHIPPED: Sale.OrderStatus.DELIVERED,
    }
    if transitions.get(sale.order_status) != next_status:
        raise ValidationError("Этот переход статуса недопустим.")
    sale.order_status = next_status
    update_fields = ["order_status", "updated_at"]
    if _complete_if_ready(sale):
        update_fields.append("completed_at")
    sale.save(update_fields=update_fields)
    logger.info("Статус заказа изменён: user_id=%s sale_id=%s status=%s", actor.pk, sale.pk, next_status)
    return sale


@transaction.atomic
def mark_sale_paid(*, actor, sale_id):
    sale = Sale.objects.select_for_update().select_related("warehouse").get(pk=sale_id)
    if sale.payment_status == Sale.PaymentStatus.PAID:
        raise ValidationError("Заказ уже оплачен.")
    if sale.payment_method == Sale.PaymentMethod.CASH_POSTPAY:
        credit_sale_payment(sale=sale, actor=actor)
    elif sale.payment_method != Sale.PaymentMethod.BANK_ACCOUNT:
        raise ValidationError("Этот способ оплаты не поддерживает отложенное подтверждение.")
    sale.payment_status = Sale.PaymentStatus.PAID
    update_fields = ["payment_status", "updated_at"]
    if _complete_if_ready(sale):
        update_fields.append("completed_at")
    sale.save(update_fields=update_fields)
    logger.info("Оплата подтверждена: user_id=%s sale_id=%s", actor.pk, sale.pk)
    return sale


@transaction.atomic
def edit_postpay_sale_items(*, actor, sale_id, lines):
    """Применяет разницы stock одним блоком; существующие строки сохраняют unit_price."""
    prepared = normalise_product_lines(lines)
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.payment_method != Sale.PaymentMethod.CASH_POSTPAY:
        raise ValidationError("Редактировать можно только продажу с наличной постоплатой.")
    if sale.payment_status == Sale.PaymentStatus.PAID:
        raise ValidationError("Состав оплаченного заказа изменять нельзя.")
    if sale.order_status == Sale.OrderStatus.DELIVERED:
        raise ValidationError("Состав доставленного заказа изменять нельзя.")

    existing = {}
    for product_type, item_model, product_field in (
        ("cd", SaleCDItem, "cd"), ("tech", SaleTechItem, "tech")
    ):
        for item in item_model.objects.select_for_update().filter(sale=sale):
            existing[(product_type, getattr(item, f"{product_field}_id"))] = item
    desired = {(line["product_type"], line["product_id"]): line["quantity"] for line in prepared}
    all_lines = [
        {"product_type": product_type, "product_id": product_id, "quantity": quantity}
        for (product_type, product_id), quantity in {
            **{key: item.quantity for key, item in existing.items()}, **desired
        }.items()
    ]
    products, stocks = _locked_inventory(sale.warehouse_id, all_lines)

    for key in set(existing) | set(desired):
        old_quantity = existing[key].quantity if key in existing else 0
        new_quantity = desired.get(key, 0)
        delta = new_quantity - old_quantity
        stock = stocks.get(key)
        if stock is None:
            raise ValidationError("Остаток товара на выбранном складе не найден.")
        if delta > 0 and stock.quantity < delta:
            raise ValidationError(f"На выбранном складе недостаточно товара «{products[key].name}».")
        if delta == 0:
            continue
        old_stock_quantity = stock.quantity
        stock.quantity -= delta
        stock.full_clean()
        stock.save(update_fields=("quantity",))
        record_product_changes(
            actor=actor,
            instance=products[key],
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Продажа {sale.visible_id}",
            changes=[stock_change(
                warehouse=sale.warehouse,
                old_quantity=old_stock_quantity,
                new_quantity=stock.quantity,
            )],
        )

    for key, item in list(existing.items()):
        new_quantity = desired.get(key, 0)
        if not new_quantity:
            item.delete()
        else:
            item.quantity = new_quantity
            item.line_total = (item.unit_price * new_quantity).quantize(CENT, rounding=ROUND_HALF_UP)
            item.full_clean()
            item.save(update_fields=("quantity", "line_total"))
    for key, quantity in desired.items():
        if key in existing:
            continue
        product_type, _ = key
        product = products[key]
        price = _selected_price(product, sale.price_type)
        values = dict(
            sale=sale, quantity=quantity, unit_price=price,
            line_total=(price * quantity).quantize(CENT, rounding=ROUND_HALF_UP),
            product_name_snapshot=product.name, article_snapshot=product.sku,
        )
        if product_type == "cd":
            SaleCDItem.objects.create(cd=product, **values)
        else:
            SaleTechItem.objects.create(tech=product, **values)

    total = sum((item.line_total for item in sale.cd_items.all()), Decimal("0")) + sum(
        (item.line_total for item in sale.tech_items.all()), Decimal("0")
    )
    sale.total_amount = total.quantize(CENT, rounding=ROUND_HALF_UP)
    sale.save(update_fields=("total_amount", "updated_at"))
    logger.info("Состав продажи изменён: user_id=%s sale_id=%s total=%s", actor.pk, sale.pk, sale.total_amount)
    return sale
