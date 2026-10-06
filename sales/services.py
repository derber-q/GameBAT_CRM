"""Атомарные продажи, статусы, оплаты и изменение неоплаченной постоплаты."""
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from cash.services import credit_sale_payment, refund_sale_payment
from catalog.audit import record_product_changes, stock_change
from catalog.models import CD, ProductChangeEvent, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.services import normalise_product_lines
from warehouse.storage_services import clear_storage_locations_if_zero
from .commissions import calculate_avito_commission
from .models import Sale, SaleCDItem, SaleTechItem, SaleCustomItem

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")
ORDER_TRANSITIONS = {
    Sale.OrderStatus.CREATED: Sale.OrderStatus.ASSEMBLED,
    Sale.OrderStatus.ASSEMBLED: Sale.OrderStatus.SHIPPED,
    Sale.OrderStatus.SHIPPED: Sale.OrderStatus.DELIVERED,
}


def next_order_status(sale):
    return None if sale.is_cancelled or sale.is_completed else ORDER_TRANSITIONS.get(sale.order_status)


def can_mark_paid(sale):
    return (
        not sale.is_cancelled and sale.payment_status == Sale.PaymentStatus.UNPAID
        and sale.payment_method in (Sale.PaymentMethod.CASH_POSTPAY, Sale.PaymentMethod.BANK_ACCOUNT)
    )


@dataclass(frozen=True)
class SaleCancellationResult:
    sale: Sale
    cancelled: bool
    refund_transaction: object | None = None


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
            for product in product_model.objects.active().select_for_update().filter(pk__in=ids).order_by("pk")
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
        Sale.PriceType.RETAIL: "avito_price",
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


def _cash_received(value, total):
    if value in (None, ""):
        return total
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную сумму, полученную от покупателя.") from exc
    if amount < total:
        raise ValidationError("Полученная сумма не может быть меньше стоимости продажи.")
    return amount


def _commission_enabled(*, sale_type):
    """Комиссия обязательна для Avito и не зависит от переданного флага."""
    return sale_type == Sale.SaleType.AVITO


def _prepare_custom_line(line, *, sale_type):
    """Проверяет ручную строку на backend и возвращает Decimal-снимки."""
    name = str(line.get("name") or "").strip()
    if not name:
        raise ValidationError("Укажите название произвольной позиции.")
    try:
        quantity = int(line.get("quantity"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Количество произвольной позиции должно быть положительным целым числом.") from exc
    if quantity <= 0:
        raise ValidationError("Количество произвольной позиции должно быть положительным целым числом.")
    values = {}
    for field, label in (("unit_price", "цену"), ("unit_cost", "себестоимость"), ("unit_discount", "скидку")):
        try:
            raw_value = line.get(field)
            if field == "unit_discount" and raw_value in (None, ""):
                raw_value = 0
            value = Decimal(str(raw_value)).quantize(CENT, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError(f"Укажите корректную {label} произвольной позиции.") from exc
        if not value.is_finite() or value < 0:
            raise ValidationError(f"{label.capitalize()} произвольной позиции не может быть отрицательной.")
        values[field] = value
    if values["unit_discount"] > values["unit_price"]:
        raise ValidationError("Скидка произвольной позиции не может превышать её цену.")
    values.update(name=name, quantity=quantity)
    values["line_total"] = (
        (values["unit_price"] - values["unit_discount"]) * quantity
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    values["avito_commission_enabled"] = _commission_enabled(sale_type=sale_type)
    values["avito_commission_amount"] = calculate_avito_commission(
        values["line_total"], enabled=values["avito_commission_enabled"],
    )
    return values


def _line_discounts(lines):
    discounts = {}
    for line in lines:
        try:
            key = (str(line.get("product_type") or "").lower(), int(line.get("product_id")))
            discount = Decimal(str(line.get("unit_discount") or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("Укажите корректный товар и скидку.") from exc
        if not discount.is_finite() or discount < 0:
            raise ValidationError("Скидка не может быть отрицательной.")
        if key in discounts and discounts[key] != discount:
            raise ValidationError("Для повторяющихся строк одного товара укажите одинаковую скидку.")
        discounts[key] = discount
    return discounts


def _line_commission_flags(lines, *, sale_type):
    flags = {}
    for line in lines:
        try:
            key = (str(line.get("product_type") or "").lower(), int(line.get("product_id")))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Укажите корректный товар и комиссию Avito.") from exc
        flags[key] = _commission_enabled(sale_type=sale_type)
    return flags


def _commission_audit_snapshot(sale):
    rows = []
    for kind, relation, product_field in (
        ("cd", "cd_items", "cd_id"), ("tech", "tech_items", "tech_id"),
    ):
        for item in getattr(sale, relation).all():
            rows.append(
                f"{kind}:{getattr(item, product_field)}:{int(item.avito_commission_enabled)}:"
                f"{item.avito_commission_amount:.2f}"
            )
    for item in sale.custom_items.all():
        rows.append(
            f"custom:{item.pk or item.product_name_snapshot}:"
            f"{int(item.avito_commission_enabled)}:{item.avito_commission_amount:.2f}"
        )
    return ",".join(rows) or "none"


@transaction.atomic
def create_sale(
    *, actor, warehouse_id, price_type, sale_type, payment_method, lines,
    cash_received_amount=None, note="", external_prices=None,
):
    """Списывает локальный stock и для наличной продажи в той же транзакции проводит кассу."""
    consignment_lines = [line for line in lines if line.get("product_type") == "consignment"]
    product_lines = [line for line in lines if line.get("product_type") in ("cd", "tech")]
    _validate_choice(price_type, Sale.PriceType, "Выберите тип цены.")
    _validate_choice(sale_type, Sale.SaleType, "Выберите тип продажи.")
    _validate_choice(payment_method, Sale.PaymentMethod, "Выберите способ оплаты.")
    custom_prepared = [
        _prepare_custom_line(line, sale_type=sale_type)
        for line in lines if line.get("product_type") == "custom"
    ]
    discounts = _line_discounts(product_lines)
    commission_flags = _line_commission_flags(product_lines, sale_type=sale_type)
    if not product_lines and not custom_prepared and not consignment_lines:
        raise ValidationError("Добавьте хотя бы один товар, позицию реализации или произвольную позицию.")
    prepared = normalise_product_lines(product_lines) if product_lines else []
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    products, stocks = _locked_inventory(warehouse.pk, prepared) if prepared else ({}, {})
    priced_lines = []
    total = Decimal("0")
    for line in prepared:
        key = (line["product_type"], line["product_id"])
        product = products[key]
        stock = stocks.get(key)
        if stock is None or stock.quantity < line["quantity"]:
            available = stock.quantity if stock is not None else 0
            raise ValidationError(
                f"На выбранном складе недостаточно товара «{product.name}»: доступно только {available} шт."
            )
        if external_prices is not None:
            if sale_type != Sale.SaleType.YANDEX_MARKET or payment_method != Sale.PaymentMethod.BANK_ACCOUNT:
                raise ValidationError("Внешние снимки цен предназначены для заказов Маркета.")
            try:
                line_total = Decimal(str(external_prices[key])).quantize(CENT)
            except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
                raise ValidationError("Отсутствует корректная стоимость строки внешнего заказа.") from exc
            if not line_total.is_finite() or line_total < 0:
                raise ValidationError("Некорректная стоимость строки внешнего заказа.")
            price = (line_total / line["quantity"]).quantize(CENT, rounding=ROUND_HALF_UP)
        else:
            price = _selected_price(product, price_type)
            discount = discounts[key]
            if discount > price:
                raise ValidationError(f"Скидка на товар «{product.name}» не может превышать цену.")
            line_total = ((price - discount) * line["quantity"]).quantize(CENT, rounding=ROUND_HALF_UP)
        if external_prices is not None:
            discount = Decimal("0.00")
        commission_enabled = commission_flags[key]
        commission_amount = calculate_avito_commission(
            line_total, enabled=commission_enabled,
        )
        priced_lines.append((
            line, product, stock, price, discount, line_total,
            commission_enabled, commission_amount,
        ))
        total += line_total

    total += sum((line["line_total"] for line in custom_prepared), Decimal("0"))
    if consignment_lines:
        from consignment.services import quote_consignment_sale_lines
        total += quote_consignment_sale_lines(consignment_lines)

    note = str(note or "").strip()
    if any(discounts.values()) or any(line["unit_discount"] for line in custom_prepared):
        if not note:
            raise ValidationError("При использовании скидки обязательно укажите примечание к продаже.")
    immediate_cash = payment_method == Sale.PaymentMethod.CASH
    actual_received = _cash_received(cash_received_amount, total) if immediate_cash else None
    extra_cash = (actual_received - total).quantize(CENT) if actual_received is not None else Decimal("0.00")
    sale = Sale.objects.create(
        warehouse=warehouse,
        price_type=price_type,
        sale_type=sale_type,
        payment_method=payment_method,
        order_status=Sale.OrderStatus.DELIVERED if immediate_cash else Sale.OrderStatus.CREATED,
        payment_status=Sale.PaymentStatus.PAID if immediate_cash else Sale.PaymentStatus.UNPAID,
        completed_at=timezone.now() if immediate_cash else None,
        total_amount=total,
        cash_received_amount=actual_received,
        extra_cash_amount=extra_cash,
        note=note,
        created_by=actor,
    )
    sale.visible_id = f"SALE-{sale.pk:06d}"
    sale.save(update_fields=("visible_id",))

    cd_items, tech_items = [], []
    for (
        line, product, stock, price, discount, line_total,
        commission_enabled, commission_amount,
    ) in priced_lines:
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
        clear_storage_locations_if_zero(
            stock=stock,
            actor=actor,
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Продажа {sale.visible_id}",
        )
        values = dict(
            sale=sale, quantity=line["quantity"], unit_price=price, unit_discount=discount,
            line_total=line_total,
            avito_commission_enabled=commission_enabled,
            avito_commission_amount=commission_amount,
            product_name_snapshot=product.name, article_snapshot=product.sku,
            unit_cost_snapshot=product.cost,
        )
        if line["product_type"] == "cd":
            cd_items.append(SaleCDItem(cd=product, **values))
        else:
            tech_items.append(SaleTechItem(tech=product, **values))
    SaleCDItem.objects.bulk_create(cd_items)
    SaleTechItem.objects.bulk_create(tech_items)
    SaleCustomItem.objects.bulk_create([
        SaleCustomItem(
            sale=sale, quantity=line["quantity"], unit_price=line["unit_price"],
            unit_discount=line["unit_discount"], line_total=line["line_total"],
            avito_commission_enabled=line["avito_commission_enabled"],
            avito_commission_amount=line["avito_commission_amount"],
            unit_cost_snapshot=line["unit_cost"],
            product_name_snapshot=line["name"], article_snapshot="",
        ) for line in custom_prepared
    ])
    if consignment_lines:
        from consignment.services import consume_consignment_sale_lines
        consume_consignment_sale_lines(actor=actor, sale=sale, lines=consignment_lines)
    if immediate_cash:
        credit_sale_payment(sale=sale, actor=actor)
    total_discount = sum(
        (discount * line["quantity"] for line, _, _, _, discount, _, _, _ in priced_lines),
        Decimal("0.00"),
    ) + sum(
        (line["unit_discount"] * line["quantity"] for line in custom_prepared),
        Decimal("0.00"),
    )
    logger.info(
        "Продажа создана: user_id=%s sale_id=%s warehouse_id=%s total=%s payment=%s "
        "cash_received=%s extra_cash=%s discount=%s avito_commissions=%s note=%s",
        getattr(actor, "pk", None), sale.pk, warehouse.pk, total, payment_method,
        actual_received, extra_cash, total_discount, _commission_audit_snapshot(sale), bool(sale.note),
    )
    return sale


@transaction.atomic
def advance_order_status(*, actor, sale_id, next_status, _market=False):
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if not _market and hasattr(sale, "yandex_order"):
        raise ValidationError("Статус этого заказа изменяется через блок Яндекс Маркета.")
    if sale.is_cancelled:
        raise ValidationError("Отменённую продажу изменять нельзя.")
    if ORDER_TRANSITIONS.get(sale.order_status) != next_status:
        raise ValidationError("Этот переход статуса недопустим.")
    sale.order_status = next_status
    update_fields = ["order_status", "updated_at"]
    if _complete_if_ready(sale):
        update_fields.append("completed_at")
    sale.save(update_fields=update_fields)
    logger.info("Статус заказа изменён: user_id=%s sale_id=%s status=%s", actor.pk, sale.pk, next_status)
    return sale


@transaction.atomic
def set_sale_payment_method(*, actor, sale_id, payment_method):
    """Выбор сотрудника не подтверждает оплату и не создаёт кассовую операцию."""
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.is_cancelled or sale.payment_status != Sale.PaymentStatus.UNPAID:
        raise ValidationError("Способ оплаты можно выбрать только для действующего неоплаченного заказа.")
    if sale.payment_method != Sale.PaymentMethod.UNDEFINED:
        raise ValidationError("Способ оплаты уже определён.")
    if payment_method not in (Sale.PaymentMethod.CASH_POSTPAY, Sale.PaymentMethod.BANK_ACCOUNT):
        raise ValidationError("Выберите наличные с последующим подтверждением или банковский счёт.")
    sale.payment_method = payment_method
    sale.full_clean()
    sale.save(update_fields=("payment_method", "updated_at"))
    logger.info("Выбран способ оплаты: user_id=%s sale_id=%s payment_method=%s", actor.pk, sale.pk, payment_method)
    return sale


@transaction.atomic
def mark_sale_paid(*, actor, sale_id, cash_received_amount=None):
    sale = Sale.objects.select_for_update().select_related("warehouse").get(pk=sale_id)
    if sale.is_cancelled:
        raise ValidationError("Отменённую продажу оплачивать нельзя.")
    if sale.payment_status == Sale.PaymentStatus.PAID:
        raise ValidationError("Заказ уже оплачен.")
    if sale.payment_method == Sale.PaymentMethod.CASH_POSTPAY:
        sale.cash_received_amount = _cash_received(cash_received_amount, sale.total_amount)
        sale.extra_cash_amount = (sale.cash_received_amount - sale.total_amount).quantize(CENT)
        credit_sale_payment(sale=sale, actor=actor)
    elif sale.payment_method != Sale.PaymentMethod.BANK_ACCOUNT:
        raise ValidationError("Этот способ оплаты не поддерживает отложенное подтверждение.")
    sale.payment_status = Sale.PaymentStatus.PAID
    update_fields = ["payment_status", "updated_at"]
    if sale.payment_method == Sale.PaymentMethod.CASH_POSTPAY:
        update_fields.extend(("cash_received_amount", "extra_cash_amount"))
    if _complete_if_ready(sale):
        update_fields.append("completed_at")
    sale.save(update_fields=update_fields)
    logger.info(
        "Оплата подтверждена: user_id=%s sale_id=%s cash_received=%s extra_cash=%s",
        actor.pk, sale.pk, sale.cash_received_amount, sale.extra_cash_amount,
    )
    return sale


@transaction.atomic
def update_sale_note(*, actor, sale_id, note):
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    old_note = sale.note
    sale.note = str(note or "").strip()
    sale.save(update_fields=("note", "updated_at"))
    logger.info(
        "Примечание продажи изменено: user_id=%s sale_id=%s old_length=%s new_length=%s",
        actor.pk, sale.pk, len(old_note), len(sale.note),
    )
    return sale


@transaction.atomic
def edit_postpay_sale_items(*, actor, sale_id, lines, note=None):
    """Применяет разницы stock одним блоком; существующие строки сохраняют unit_price."""
    custom_lines = [line for line in lines if line.get("product_type") == "custom"]
    consignment_lines = [line for line in lines if line.get("product_type") == "consignment"]
    product_lines = [line for line in lines if line.get("product_type") in ("cd", "tech")]
    discounts = _line_discounts(product_lines)
    if not product_lines and not custom_lines and not consignment_lines:
        raise ValidationError("Добавьте хотя бы один товар, позицию реализации или произвольную позицию.")
    prepared = normalise_product_lines(product_lines) if product_lines else []
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if hasattr(sale, "yandex_order"):
        raise ValidationError("Состав заказа Маркета нельзя редактировать как обычную продажу.")
    if sale.is_cancelled:
        raise ValidationError("Состав отменённой продажи изменять нельзя.")
    if sale.payment_method != Sale.PaymentMethod.CASH_POSTPAY:
        raise ValidationError("Редактировать можно только продажу с наличной постоплатой.")
    if sale.payment_status == Sale.PaymentStatus.PAID:
        raise ValidationError("Состав оплаченного заказа изменять нельзя.")
    if sale.order_status == Sale.OrderStatus.DELIVERED:
        raise ValidationError("Состав доставленного заказа изменять нельзя.")
    custom_prepared = [
        _prepare_custom_line(line, sale_type=sale.sale_type) for line in custom_lines
    ]
    commission_flags = _line_commission_flags(product_lines, sale_type=sale.sale_type)
    old_commission_snapshot = _commission_audit_snapshot(sale)
    resulting_note = sale.note if note is None else str(note or "").strip()
    from consignment.services import (
        consume_consignment_sale_lines, quote_consignment_sale_lines, restore_consignment_sale_lines,
    )
    restore_consignment_sale_lines(actor=actor, sale=sale, delete=True)
    if consignment_lines:
        quote_consignment_sale_lines(consignment_lines)

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
        clear_storage_locations_if_zero(
            stock=stock,
            actor=actor,
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Продажа {sale.visible_id}",
        )

    for key, item in list(existing.items()):
        new_quantity = desired.get(key, 0)
        if not new_quantity:
            item.delete()
        else:
            item.quantity = new_quantity
            item.unit_discount = discounts[key]
            if item.unit_discount > item.unit_price:
                raise ValidationError(f"Скидка на товар «{item.product_name_snapshot}» не может превышать цену.")
            item.line_total = ((item.unit_price - item.unit_discount) * new_quantity).quantize(CENT, rounding=ROUND_HALF_UP)
            item.avito_commission_enabled = commission_flags[key]
            item.avito_commission_amount = calculate_avito_commission(
                item.line_total, enabled=item.avito_commission_enabled,
            )
            item.full_clean()
            item.save(update_fields=(
                "quantity", "unit_discount", "line_total",
                "avito_commission_enabled", "avito_commission_amount",
            ))
    for key, quantity in desired.items():
        if key in existing:
            continue
        product_type, _ = key
        product = products[key]
        price = _selected_price(product, sale.price_type)
        discount = discounts[key]
        if discount > price:
            raise ValidationError(f"Скидка на товар «{product.name}» не может превышать цену.")
        values = dict(
            sale=sale, quantity=quantity, unit_price=price, unit_discount=discount,
            line_total=((price - discount) * quantity).quantize(CENT, rounding=ROUND_HALF_UP),
            product_name_snapshot=product.name, article_snapshot=product.sku,
            unit_cost_snapshot=product.cost,
        )
        values["avito_commission_enabled"] = commission_flags[key]
        values["avito_commission_amount"] = calculate_avito_commission(
            values["line_total"], enabled=values["avito_commission_enabled"],
        )
        if product_type == "cd":
            SaleCDItem.objects.create(cd=product, **values)
        else:
            SaleTechItem.objects.create(tech=product, **values)

    SaleCustomItem.objects.filter(sale=sale).delete()
    SaleCustomItem.objects.bulk_create([
        SaleCustomItem(
            sale=sale, quantity=line["quantity"], unit_price=line["unit_price"],
            unit_discount=line["unit_discount"], line_total=line["line_total"],
            avito_commission_enabled=line["avito_commission_enabled"],
            avito_commission_amount=line["avito_commission_amount"],
            unit_cost_snapshot=line["unit_cost"],
            product_name_snapshot=line["name"], article_snapshot="",
        ) for line in custom_prepared
    ])
    if consignment_lines:
        consume_consignment_sale_lines(actor=actor, sale=sale, lines=consignment_lines)

    total = sum((item.line_total for item in sale.cd_items.all()), Decimal("0")) + sum(
        (item.line_total for item in sale.tech_items.all()), Decimal("0")
    ) + sum((item.line_total for item in sale.custom_items.all()), Decimal("0"))
    total += sum((item.line_total for item in sale.consignment_items.all()), Decimal("0"))
    if any(discounts.values()) or any(line["unit_discount"] for line in custom_prepared):
        if not resulting_note:
            raise ValidationError("При использовании скидки обязательно укажите примечание к продаже.")
    sale.total_amount = total.quantize(CENT, rounding=ROUND_HALF_UP)
    sale.note = resulting_note
    sale.save(update_fields=("total_amount", "note", "updated_at"))
    total_discount = sum(
        (item.unit_discount * item.quantity for item in sale.cd_items.all()), Decimal("0.00")
    ) + sum(
        (item.unit_discount * item.quantity for item in sale.tech_items.all()), Decimal("0.00")
    ) + sum(
        (item.unit_discount * item.quantity for item in sale.custom_items.all()), Decimal("0.00")
    )
    logger.info(
        "Состав продажи изменён: user_id=%s sale_id=%s total=%s discount=%s "
        "avito_commissions_old=%s avito_commissions_new=%s note=%s",
        actor.pk, sale.pk, sale.total_amount, total_discount,
        old_commission_snapshot, _commission_audit_snapshot(sale), bool(sale.note),
    )
    return sale


@transaction.atomic
def cancel_sale(*, actor, sale_id, comment, _market=False, restore_stock=True):
    """Возвращает товары и фактическую оплату, сохраняя продажу и все исходные строки."""
    comment = str(comment or "").strip()
    if not comment:
        raise ValidationError("Укажите причину отмены продажи.")
    sale = Sale.objects.select_for_update().select_related("warehouse").get(pk=sale_id)
    if not _market and hasattr(sale, "yandex_order"):
        raise ValidationError("Отмените заказ через блок Яндекс Маркета; отправленный товар принимается отдельным возвратом.")
    if not restore_stock and not _market:
        raise ValidationError("Отмена обычной продажи должна восстановить товар.")
    if sale.is_cancelled:
        return SaleCancellationResult(sale=sale, cancelled=False)
    Warehouse.objects.select_for_update().get(pk=sale.warehouse_id)

    lines = []
    locked_items = []
    has_consignment_snapshots = sale.consignment_items.exists()
    for product_type, item_model, product_field in (
        ("cd", SaleCDItem, "cd"), ("tech", SaleTechItem, "tech")
    ):
        items = list(
            item_model.objects.select_for_update().select_related(product_field)
            .filter(sale=sale).order_by(product_field)
        )
        if not (sale.sale_type == Sale.SaleType.CONSIGNMENT and has_consignment_snapshots):
            locked_items.extend((product_type, product_field, item) for item in items)
        if not (sale.sale_type == Sale.SaleType.CONSIGNMENT and has_consignment_snapshots):
            lines.extend({
                "product_type": product_type,
                "product_id": getattr(item, f"{product_field}_id"),
                "quantity": item.quantity,
            } for item in items)
    if not lines and not SaleCustomItem.objects.filter(sale=sale).exists():
        if not sale.consignment_items.exists():
            raise ValidationError("В продаже нет товарных позиций для возврата.")
    products, stocks = _locked_inventory(sale.warehouse_id, lines) if lines else ({}, {})

    refund_transaction = None
    refund_amount = Decimal("0.00")
    if sale.payment_status == Sale.PaymentStatus.PAID:
        if sale.payment_method in (Sale.PaymentMethod.CASH, Sale.PaymentMethod.CASH_POSTPAY):
            refund_transaction = refund_sale_payment(
                sale=sale, actor=actor, comment=f"Отмена {sale.visible_id}: {comment}",
            )
            refund_amount = refund_transaction.amount
        elif sale.payment_method == Sale.PaymentMethod.BANK_ACCOUNT:
            refund_amount = sale.total_amount

    for product_type, product_field, item in (locked_items if restore_stock else []):
        key = (product_type, getattr(item, f"{product_field}_id"))
        product = products[key]
        stock = stocks.get(key)
        if stock is None:
            _, stock_model, _, _ = _configuration(product_type)
            stock = stock_model(warehouse_id=sale.warehouse_id, **{product_field: product})
        old_quantity = stock.quantity
        stock.quantity += item.quantity
        stock.full_clean()
        stock.save()
        record_product_changes(
            actor=actor,
            instance=product,
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Отмена продажи {sale.visible_id}",
            changes=[stock_change(
                warehouse=sale.warehouse,
                old_quantity=old_quantity,
                new_quantity=stock.quantity,
            )],
        )

    if restore_stock and sale.consignment_items.exists():
        from consignment.services import restore_consignment_sale_lines
        restore_consignment_sale_lines(actor=actor, sale=sale)

    sale.cancelled_at = timezone.now()
    sale.cancelled_by = actor
    sale.cancellation_comment = comment
    sale.refunded_amount = refund_amount
    sale.full_clean()
    sale.save(update_fields=(
        "cancelled_at", "cancelled_by", "cancellation_comment", "refunded_amount", "updated_at",
    ))
    logger.info(
        "Продажа отменена: user_id=%s sale_id=%s warehouse_id=%s refund=%s payment=%s",
        actor.pk, sale.pk, sale.warehouse_id, refund_amount, sale.payment_method,
    )
    return SaleCancellationResult(
        sale=sale, cancelled=True, refund_transaction=refund_transaction,
    )
