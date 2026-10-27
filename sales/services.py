"""Атомарные продажи, статусы, оплаты и изменение неоплаченной постоплаты."""
import logging
import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from cash.services import credit_sale_payment, refund_sale_payment
from catalog.audit import field_change, record_product_changes, stock_change
from catalog.models import CD, ProductChangeEvent, Tech, SystemProduct
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.services import normalise_product_lines
from warehouse.storage_services import clear_storage_locations_if_zero
from warehouse.valuation import warehouse_owned_quantity, weighted_warehouse_cost
from .commissions import calculate_avito_commission
from .models import Sale, SaleCDItem, SaleTechItem, SaleCustomItem
from partners.customers import resolve_customer
from .partner_payments import money, payment_values, record_settlement, reverse_settlement, resolve_payment_partner
from core.db_retry import retry_database_lock

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")
ORDER_TRANSITIONS = {
    Sale.OrderStatus.CREATED: Sale.OrderStatus.ASSEMBLED,
    Sale.OrderStatus.ASSEMBLED: Sale.OrderStatus.DELIVERED,
}


def next_order_status(sale):
    return None if sale.is_cancelled or sale.is_completed else ORDER_TRANSITIONS.get(sale.order_status)


def can_mark_paid(sale):
    if sale.direct_delivery:
        from orders.arrival import document_waits_finalization
        if document_waits_finalization(sale):return False
    return (
        not sale.is_cancelled and sale.payment_status == Sale.PaymentStatus.UNPAID
        and sale.is_postpayment
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


def _locked_inventory(warehouse_id, lines, *, direct_delivery=False):
    """Блокирует товары и локальные остатки; product lock синхронизирует продажи с пересчётом cost."""
    products, stocks = {}, {}
    for product_type in ("cd", "tech"):
        product_model, stock_model, _, product_field = _configuration(product_type)
        ids = {line["product_id"] for line in lines if line["product_type"] == product_type}
        products.update({
            (product_type, product.pk): product
            for product in product_model.objects.active().select_for_update().filter(pk__in=ids).order_by("pk")
        })
        if direct_delivery:
            continue
        stocks.update({
            (product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in stock_model.objects.select_for_update().filter(
                warehouse_id=warehouse_id, **{f"{product_field}_id__in": ids}
            ).order_by(product_field)
        })
    if len(products) != len({(line["product_type"], line["product_id"]) for line in lines}):
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
    if sale.is_completed:
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
    if not amount.is_finite() or amount >= Decimal("1e18"):
        raise ValidationError("Укажите корректную сумму, полученную от покупателя.")
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
        if not value.is_finite() or (field != "unit_discount" and value < 0):
            raise ValidationError(f"{label.capitalize()} произвольной позиции не может быть отрицательной.")
        values[field] = value
    if values["unit_discount"] > values["unit_price"]:
        raise ValidationError("Скидка произвольной позиции не может превышать её цену.")
    values.update(name=name, quantity=quantity)
    try:
        values["line_total"] = (
            (values["unit_price"] - values["unit_discount"]) * quantity
        ).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValidationError("Сумма строки превышает допустимый размер.") from exc
    values["avito_commission_enabled"] = _commission_enabled(sale_type=sale_type)
    values["avito_commission_amount"] = calculate_avito_commission(
        values["line_total"], enabled=values["avito_commission_enabled"],
    )
    return values


def _sale_product_lines(lines):
    """Сохраняет строки продажи; складской normalizer вызывается отдельно для каждой."""
    prepared = []
    for source in lines:
        line = normalise_product_lines([source])[0]
        try:
            discount = Decimal(str(source.get("unit_discount") or 0)).quantize(CENT, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("Укажите корректную скидку или доплату.") from exc
        if not discount.is_finite():
            raise ValidationError("Укажите корректную скидку или доплату.")
        line.update(unit_discount=discount, note=str(source.get("line_note") or "").strip(),
                    item_id=source.get("item_id"))
        prepared.append(line)
    return prepared


def _product_quantities(lines):
    totals = defaultdict(int)
    for line in lines:
        totals[(line["product_type"], line["product_id"])] += line["quantity"]
    return totals


MIXED_OPERATION_ERROR = "Цифровые товары и расходы необходимо оформлять отдельной продажей."


def _prepare_manual_lines(lines, *, sale_type, note):
    """Определяет режим по фактическому составу, проверяя каждый входной тип."""
    allowed = {"cd", "tech", "custom", "consignment", "system"}
    if any(line.get("product_type") not in allowed for line in lines):
        raise ValidationError("Неизвестный тип позиции продажи.")
    system_lines = [line for line in lines if line.get("product_type") == "system"]
    kinds = {line.get("system_kind") for line in system_lines}
    if kinds and (len(kinds) != 1 or len(system_lines) != len(lines)):
        raise ValidationError(MIXED_OPERATION_ERROR)
    operation = next(iter(kinds)) if kinds else Sale.OperationKind.NORMAL
    if kinds and operation not in SystemProduct.Kind.values:
        raise ValidationError("Неизвестная системная позиция.")
    if operation == Sale.OperationKind.DIGITAL_PRODUCT and not str(note or "").strip():
        raise ValidationError("Для продажи цифрового товара необходимо заполнить примечание.")
    products = SystemProduct.objects.in_bulk(kinds) if kinds else {}
    if kinds and len(products) != len(kinds):
        raise ValidationError("Системная позиция не инициализирована.")
    prepared = []
    for source in lines:
        if source.get("product_type") not in {"custom", "system"}:
            continue
        line = dict(source)
        kind = line.get("system_kind") if line["product_type"] == "system" else None
        if kind:
            line["name"] = products[kind].name
            if kind == SystemProduct.Kind.EXPENSE:
                line.setdefault("unit_price", "0")
        values = _prepare_custom_line(line, sale_type=(Sale.SaleType.RETAIL if kind == "EXPENSE" else sale_type))
        values["system_kind"] = kind
        if kind and (
            values["quantity"] > 2_147_483_647
            or any(abs(values[field]) >= Decimal("1e18") for field in ("unit_price", "unit_cost", "line_total"))
            or values["unit_cost"] * values["quantity"] >= Decimal("1e18")
        ):
            raise ValidationError("Количество или сумма системной позиции превышает допустимый размер.")
        if kind and values["unit_discount"]:
            raise ValidationError("Скидка системной позиции не используется; укажите итоговую цену.")
        if kind == "EXPENSE" and values["unit_price"] != 0:
            raise ValidationError("Цена расхода всегда равна 0 ₽.")
        prepared.append(values)
    return operation, prepared


def _validate_partner_debt(*, partner, sale_type, operation, total, received):
    if partner is None or sale_type != Sale.SaleType.WHOLESALE:
        raise ValidationError('Продажа в долг доступна только партнёру из справочника в оптовой продаже.')
    if operation == Sale.OperationKind.EXPENSE or total <= 0:
        raise ValidationError('Для продажи в долг нужна положительная стоимость товаров.')
    if received not in (None, '') and money(received) != 0:
        raise ValidationError('При продаже в долг полученная сумма должна быть равна нулю.')


def _validate_expense_received(operation, amount):
    if operation == Sale.OperationKind.EXPENSE and amount not in (None, ""):
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError("Для расхода полученная от покупателя сумма равна нулю.") from exc
        if not value.is_finite() or value != 0:
            raise ValidationError("Для расхода полученная от покупателя сумма равна нулю.")


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


@retry_database_lock
def create_sale(
    *, actor, warehouse_id, price_type, sale_type, payment_method, lines,
    cash_received_amount=None, note="", external_prices=None, creation_key=None,
    partner_id=None, partner_name="", settlement_confirmation="",
):
    """Обычная продажа; заказы и цены Маркета доступны только внутреннему импорту."""
    if sale_type == Sale.SaleType.YANDEX_MARKET or price_type == Sale.PriceType.YANDEX_MARKET:
        raise ValidationError("Продажи и цены Яндекс Маркета доступны только через автоматическую интеграцию.")
    return _create_sale(actor=actor, warehouse_id=warehouse_id, price_type=price_type,
        sale_type=sale_type, payment_method=payment_method, lines=lines,
        cash_received_amount=cash_received_amount, note=note, external_prices=external_prices, creation_key=creation_key,
        partner_id=partner_id, partner_name=partner_name, settlement_confirmation=settlement_confirmation)


@transaction.atomic
def create_market_sale(*, order, lines, external_prices):
    """Доверенный путь импорта: настройки берутся из существующего заказа, а не HTTP."""
    from yandex_market.models import OrderMetadata
    if not isinstance(order, OrderMetadata) or not order.pk:
        raise ValidationError("Для автоматической продажи нужен существующий заказ Маркета.")
    stored = OrderMetadata.objects.select_for_update().select_related('integration').get(pk=order.pk)
    if stored.sale_id or stored.fake:
        raise ValidationError("Заказ уже связан с продажей либо является тестовым.")
    integration = stored.integration
    if not integration.operator_id or not integration.fulfillment_warehouse_id:
        raise ValidationError("Настройте склад выполнения и ответственного сотрудника Маркета.")
    return _create_sale(actor=integration.operator, warehouse_id=integration.fulfillment_warehouse_id,
        price_type=Sale.PriceType.YANDEX_MARKET, sale_type=Sale.SaleType.YANDEX_MARKET,
        payment_method=Sale.PaymentMethod.BANK_TRANSFER_POSTPAY, lines=lines, external_prices=external_prices,
        note=f"Заказ Яндекс Маркета №{stored.order_id}. Выплата подтверждается отдельно.")


@transaction.atomic
def _create_sale(
    *, actor, warehouse_id, price_type, sale_type, payment_method, lines,
    cash_received_amount=None, note="", external_prices=None, creation_key=None,
    partner_id=None, partner_name="", settlement_confirmation="", _direct_rows=None, _prepaid=Decimal('0.00'),
):
    """Списывает локальный stock и для наличной продажи в той же транзакции проводит кассу."""
    fingerprint = ""
    if creation_key:
        try:
            creation_key = uuid.UUID(str(creation_key))
        except (ValueError, TypeError) as exc:
            raise ValidationError("Некорректный ключ формы продажи.") from exc
        fingerprint = hashlib.sha256(json.dumps({
            "actor": actor.pk, "warehouse": str(warehouse_id), "price": price_type,
            "type": sale_type, "payment": payment_method, "lines": lines,
            "received": cash_received_amount, "note": note,
            "partner_id": str(partner_id or ''), "partner_name": partner_name,
        }, sort_keys=True, default=str).encode()).hexdigest()
        existing = Sale.objects.filter(creation_key=creation_key).first()
        if existing:
            if existing.created_by_id != actor.pk or existing.creation_fingerprint != fingerprint:
                raise ValidationError("Эта форма уже использована для другой продажи. Откройте новую форму.")
            return existing
    consignment_lines = [line for line in lines if line.get("product_type") == "consignment"]
    product_lines = [line for line in lines if line.get("product_type") in ("cd", "tech")]
    _validate_choice(price_type, Sale.PriceType, "Выберите тип цены.")
    _validate_choice(sale_type, Sale.SaleType, "Выберите тип продажи.")
    _validate_choice(payment_method, Sale.PaymentMethod, "Выберите способ оплаты.")
    if sale_type != Sale.SaleType.WHOLESALE and (partner_id or partner_name):
        raise ValidationError('Заказчик в этой форме доступен только для оптовой продажи.')
    partner, customer_name = resolve_customer(partner_id=partner_id, partner_name=partner_name,
        required=sale_type == Sale.SaleType.WHOLESALE)
    if price_type == Sale.PriceType.WHOLESALE and sale_type != Sale.SaleType.WHOLESALE:
        raise ValidationError("Оптовая цена доступна только для оптовой продажи.")
    operation, custom_prepared = _prepare_manual_lines(lines, sale_type=sale_type, note=note)
    _validate_expense_received(operation, cash_received_amount)
    if operation != Sale.OperationKind.NORMAL and (external_prices is not None or sale_type == Sale.SaleType.CONSIGNMENT or price_type == Sale.PriceType.CONSIGNMENT):
        raise ValidationError("Системные позиции нельзя оформлять как реализацию или внешний заказ.")
    if not product_lines and not custom_prepared and not consignment_lines:
        raise ValidationError("Добавьте хотя бы один товар, позицию реализации или произвольную позицию.")
    prepared = _sale_product_lines(product_lines)
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    direct = _direct_rows is not None
    if direct and (sale_type != Sale.SaleType.WHOLESALE or price_type != Sale.PriceType.WHOLESALE or custom_prepared or consignment_lines):
        raise ValidationError('Прямая отгрузка доступна только для товаров клиентского заказа рейса.')
    products, stocks = _locked_inventory(warehouse.pk, prepared) if prepared else ({}, {})
    warehouse_prepared = [line for index, line in enumerate(prepared)
                          if not direct or _direct_rows[index].get('origin', 'trip') == 'warehouse']
    for key, quantity in _product_quantities(warehouse_prepared).items():
        if key not in stocks or stocks[key].quantity < quantity:
            available = stocks[key].quantity if key in stocks else 0
            raise ValidationError(f"На выбранном складе недостаточно товара «{products[key].name}»: доступно только {available} шт.")
    priced_lines = []
    total = Decimal("0")
    for index, line in enumerate(prepared):
        line_direct = direct and _direct_rows[index].get('origin', 'trip') != 'warehouse'
        key = (line["product_type"], line["product_id"])
        product = products[key]
        stock = stocks.get(key)
        if not line_direct and (stock is None or stock.quantity < line["quantity"]):
            available = stock.quantity if stock is not None else 0
            raise ValidationError(
                f"На выбранном складе недостаточно товара «{product.name}»: доступно только {available} шт."
            )
        if external_prices is not None:
            if sale_type != Sale.SaleType.YANDEX_MARKET or payment_method != Sale.PaymentMethod.BANK_TRANSFER_POSTPAY:
                raise ValidationError("Внешние снимки цен предназначены для заказов Маркета.")
            try:
                line_total = Decimal(str(external_prices[key])).quantize(CENT)
            except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
                raise ValidationError("Отсутствует корректная стоимость строки внешнего заказа.") from exc
            if not line_total.is_finite() or line_total < 0:
                raise ValidationError("Некорректная стоимость строки внешнего заказа.")
            price = (line_total / line["quantity"]).quantize(CENT, rounding=ROUND_HALF_UP)
        else:
            price = Decimal(_direct_rows[index]['unit_price']) if direct else _selected_price(product, price_type)
            discount = line["unit_discount"]
            if discount > price:
                raise ValidationError(f"Скидка на товар «{product.name}» не может превышать цену.")
            line_total = ((price - discount) * line["quantity"]).quantize(CENT, rounding=ROUND_HALF_UP)
        if external_prices is not None:
            discount = Decimal("0.00")
        commission_enabled = _commission_enabled(sale_type=sale_type)
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
    if operation != Sale.OperationKind.NORMAL and total >= Decimal("1e18"):
        raise ValidationError("Сумма системной операции превышает допустимый размер.")
    if any(line["unit_discount"] for line in prepared + custom_prepared):
        if not note:
            raise ValidationError("При использовании скидки или доплаты обязательно укажите примечание к продаже.")
    method = Sale.PaymentMethod(payment_method)
    if (method == Sale.PaymentMethod.CASH and partner is not None and total > 0
            and cash_received_amount not in (None, '') and money(cash_received_amount) == 0):
        method = Sale.PaymentMethod.PARTNER_DEBT
    if _prepaid and (not method.is_cash_payment or method == Sale.PaymentMethod.PARTNER_DEBT):
        raise ValidationError('По заказу уже внесена предоплата наличными. Выберите наличную оплату или наличную постоплату.')
    if method == Sale.PaymentMethod.PARTNER_DEBT:
        _validate_partner_debt(partner=partner, sale_type=sale_type, operation=operation,
            total=total, received=cash_received_amount)
    payment_method = method.value
    immediate_payment = method != Sale.PaymentMethod.UNDEFINED and not method.is_postpayment
    actual_received, extra_cash, repayment, offset = (None, Decimal('0.00'), Decimal('0.00'), Decimal('0.00'))
    if method == Sale.PaymentMethod.PARTNER_DEBT:
        actual_received = Decimal('0.00')
    elif immediate_payment:
        actual_received, extra_cash, repayment, offset = payment_values(actor=actor, sale_type=sale_type,
            partner=partner, total=total, received=cash_received_amount, note=note,
            confirmation=settlement_confirmation, creation_key=creation_key)
    if actual_received is not None and actual_received < _prepaid:
        raise ValidationError('Полученная сумма с учётом предоплаты не может быть меньше уже внесённой предоплаты.')
    sale = Sale.objects.create(
        direct_delivery=direct, procurement_prepaid_amount=_prepaid,
        operation_kind=operation, creation_key=creation_key, creation_fingerprint=fingerprint,
        warehouse=warehouse,
        price_type=price_type,
        sale_type=sale_type,
        payment_method=payment_method,
        order_status=Sale.OrderStatus.DELIVERED if immediate_payment else Sale.OrderStatus.CREATED,
        payment_status=Sale.PaymentStatus.PAID if immediate_payment else Sale.PaymentStatus.UNPAID,
        paid_at=timezone.now() if immediate_payment else None,
        paid_by=actor if immediate_payment else None,
        total_amount=total,
        cash_received_amount=actual_received,
        extra_cash_amount=extra_cash,
        note=note,
        created_by=actor,
        partner=partner, partner_name_snapshot=customer_name,
        debt_repayment_amount=repayment, debt_offset_amount=offset,
    )
    if _complete_if_ready(sale):
        sale.save(update_fields=("completed_at",))
    sale.visible_id = f"SALE-{sale.pk:06d}"
    sale.save(update_fields=("visible_id",))
    record_settlement(sale=sale, actor=actor)

    cd_items, tech_items = [], []
    for index, (
        line, product, stock, price, discount, line_total,
        commission_enabled, commission_amount,
    ) in enumerate(priced_lines):
        line_direct = direct and _direct_rows[index].get('origin', 'trip') != 'warehouse'
        if not line_direct:
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
            sale=sale, quantity=line["quantity"], unit_price=price, unit_discount=discount, note=line["note"],
            line_total=line_total,
            avito_commission_enabled=commission_enabled,
            avito_commission_amount=commission_amount,
            product_name_snapshot=product.name, article_snapshot=product.sku,
            unit_cost_snapshot=Decimal(_direct_rows[index]['unit_cost']) if line_direct else product.cost,
            is_direct_delivery=line_direct,
            trip_cost_row_id=_direct_rows[index].get('trip_cost_row_id') if direct else None,
            trip_cost_slot=_direct_rows[index].get('trip_cost_slot', 0) if direct else 0,
        )
        if line["product_type"] == "cd":
            cd_items.append(SaleCDItem(cd=product, **values))
        else:
            tech_items.append(SaleTechItem(tech=product, **values))
    SaleCDItem.objects.bulk_create(cd_items)
    SaleTechItem.objects.bulk_create(tech_items)
    SaleCustomItem.objects.bulk_create([
        SaleCustomItem(
            sale=sale, system_product_id=line["system_kind"], quantity=line["quantity"], unit_price=line["unit_price"],
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
    if immediate_payment and sale.is_cash_payment and operation != Sale.OperationKind.EXPENSE:
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
        "cash_received=%s extra_cash=%s discount=%s avito_commissions=%s note=%s operation=%s",
        getattr(actor, "pk", None), sale.pk, warehouse.pk, total, payment_method,
        actual_received, extra_cash, total_discount, _commission_audit_snapshot(sale), bool(sale.note), operation,
    )
    return sale


@transaction.atomic
def advance_order_status(*, actor, sale_id, next_status, _market=False):
    from orders.arrival import lock_document_trip
    lock_document_trip('sale',sale_id)
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    sale._trip_actor = actor
    if not _market and hasattr(sale, "yandex_order"):
        raise ValidationError("Статус этого заказа изменяется через блок Яндекс Маркета.")
    if sale.is_cancelled:
        raise ValidationError("Отменённую продажу изменять нельзя.")
    if next_status not in Sale.OrderStatus.values or ORDER_TRANSITIONS.get(sale.order_status) != next_status:
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
    # Совместимость с ранее открытой формой розничного заказа.
    if payment_method == Sale.PaymentMethod.BANK_ACCOUNT:
        payment_method = Sale.PaymentMethod.BANK_TRANSFER_POSTPAY
    if payment_method not in (Sale.PaymentMethod.CASH_POSTPAY, Sale.PaymentMethod.BANK_TRANSFER_POSTPAY):
        raise ValidationError("Выберите наличную или банковскую постоплату.")
    sale.payment_method = payment_method
    sale.full_clean()
    sale.save(update_fields=("payment_method", "updated_at"))
    logger.info("Выбран способ оплаты: user_id=%s sale_id=%s payment_method=%s", actor.pk, sale.pk, payment_method)
    return sale


@retry_database_lock
@transaction.atomic
def mark_sale_paid(*, actor, sale_id, cash_received_amount=None, settlement_confirmation="", note=None,
                   settlement_partner_id=None):
    from orders.arrival import lock_document_trip
    lock_document_trip('sale',sale_id)
    sale = Sale.objects.select_for_update().select_related("warehouse").get(pk=sale_id)
    sale._trip_actor = actor
    from orders.arrival import assert_document_finalized
    assert_document_finalized(sale)
    if sale.is_cancelled:
        raise ValidationError("Отменённую продажу оплачивать нельзя.")
    if sale.payment_status == Sale.PaymentStatus.PAID:
        raise ValidationError("Заказ уже оплачен.")
    if not sale.is_postpayment:
        raise ValidationError("Этот способ оплаты не поддерживает отложенное подтверждение.")
    original_partner_id = sale.partner_id
    if settlement_partner_id not in (None, ''):
        if not actor.has_perm('sales.mark_sale_paid'):
            raise PermissionDenied('Нет права подтверждения оплаты.')
        partner = resolve_payment_partner(sale, settlement_partner_id)
        if not sale.partner_id:
            sale.partner = partner
            sale.partner_name_snapshot = partner.name
    if sale.procurement_prepaid_amount:
        received = sale.total_amount if cash_received_amount in (None, '') else money(cash_received_amount)
        if not sale.is_cash_payment or received < sale.procurement_prepaid_amount:
            raise ValidationError('Укажите наличную оплату с учётом уже внесённого аванса заказа.')
    _validate_expense_received(sale.operation_kind, cash_received_amount)
    if note is not None:
        sale.note = str(note or '').strip()
    if (sale.is_cash_payment and sale.partner_id and sale.total_amount > 0
            and cash_received_amount not in (None, '') and money(cash_received_amount) == 0):
        _validate_partner_debt(partner=sale.partner, sale_type=sale.sale_type, operation=sale.operation_kind,
            total=sale.total_amount, received=cash_received_amount)
        sale.payment_method = Sale.PaymentMethod.PARTNER_DEBT
        sale.cash_received_amount = Decimal('0.00')
    else:
        sale.cash_received_amount, sale.extra_cash_amount, sale.debt_repayment_amount, sale.debt_offset_amount = payment_values(
            actor=actor, sale_type=sale.sale_type, partner=sale.partner, total=sale.total_amount,
            received=cash_received_amount, note=sale.note, confirmation=settlement_confirmation, sale_id=sale.pk)
    record_settlement(sale=sale, actor=actor)
    if sale.is_cash_payment and sale.operation_kind != Sale.OperationKind.EXPENSE:
        if sale.cash_received_amount < sale.procurement_prepaid_amount:
            raise ValidationError('Полученная сумма с учётом предоплаты меньше уже внесённого аванса.')
        credit_sale_payment(sale=sale, actor=actor)
    sale.payment_status = Sale.PaymentStatus.PAID
    sale.paid_at = timezone.now()
    sale.paid_by = actor
    update_fields = ["payment_status", "payment_method", "updated_at", "cash_received_amount", "extra_cash_amount", "paid_at", "paid_by", "debt_repayment_amount", "debt_offset_amount", "note"]
    if sale.partner_id != original_partner_id:
        update_fields.extend(('partner', 'partner_name_snapshot'))
    if _complete_if_ready(sale):
        update_fields.append("completed_at")
    sale.save(update_fields=update_fields)
    if sale.partner_id != original_partner_id:
        logger.info('Партнёр выбран при оплате: user_id=%s sale_id=%s partner_id=%s', actor.pk, sale.pk, sale.partner_id)
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
    if (sale.debt_offset_amount or sale.debt_repayment_amount or (sale.debt_charge_amount and not sale.is_partner_debt)) and not sale.note:
        raise ValidationError('У продажи с расчётом задолженности примечание обязательно.')
    sale.save(update_fields=("note", "updated_at"))
    logger.info(
        "Примечание продажи изменено: user_id=%s sale_id=%s old_length=%s new_length=%s",
        actor.pk, sale.pk, len(old_note), len(sale.note),
    )
    return sale


@transaction.atomic
def edit_postpay_sale_items(*, actor, sale_id, lines, note=None, partner_id=None, partner_name=None):
    """Применяет разницы stock одним блоком; существующие строки сохраняют unit_price."""
    custom_lines = [line for line in lines if line.get("product_type") in ("custom", "system")]
    consignment_lines = [line for line in lines if line.get("product_type") == "consignment"]
    product_lines = [line for line in lines if line.get("product_type") in ("cd", "tech")]
    if not product_lines and not custom_lines and not consignment_lines:
        raise ValidationError("Добавьте хотя бы один товар, позицию реализации или произвольную позицию.")
    prepared = _sale_product_lines(product_lines)
    from orders.arrival import lock_document_trip
    lock_document_trip('sale',sale_id)
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if hasattr(sale, "yandex_order"):
        raise ValidationError("Состав заказа Маркета нельзя редактировать как обычную продажу.")
    if sale.is_cancelled:
        raise ValidationError("Состав отменённой продажи изменять нельзя.")
    if not sale.is_postpayment:
        raise ValidationError("Редактировать можно только продажу с постоплатой.")
    if sale.payment_status == Sale.PaymentStatus.PAID:
        raise ValidationError("Состав оплаченного заказа изменять нельзя.")
    if sale.order_status == Sale.OrderStatus.DELIVERED:
        raise ValidationError("Состав доставленного заказа изменять нельзя.")
    if sale.direct_delivery:
        from orders.fulfillment import edit_direct_sale
        return edit_direct_sale(actor=actor, sale=sale, lines=lines, note=note,
                                partner_id=partner_id, partner_name=partner_name)
    if sale.sale_type == Sale.SaleType.WHOLESALE:
        if (partner_id is not None or partner_name is not None) and not (
                partner_id is not None and str(partner_id) == str(sale.partner_id) and not partner_name):
            sale.partner, sale.partner_name_snapshot = resolve_customer(partner_id=partner_id, partner_name=partner_name or '', required=True)
        elif not sale.partner_name_snapshot:
            raise ValidationError('Для редактирования оптовой продажи укажите заказчика.')
    resulting_note = sale.note if note is None else str(note or "").strip()
    operation, custom_prepared = _prepare_manual_lines(lines, sale_type=sale.sale_type, note=resulting_note)
    sale.operation_kind = operation
    old_commission_snapshot = _commission_audit_snapshot(sale)
    resulting_note = sale.note if note is None else str(note or "").strip()
    from consignment.services import (
        consume_consignment_sale_lines, quote_consignment_sale_lines, restore_consignment_sale_lines,
    )
    restore_consignment_sale_lines(actor=actor, sale=sale, delete=True)
    if consignment_lines:
        quote_consignment_sale_lines(consignment_lines)

    existing, by_product = {}, defaultdict(list)
    for kind, model, field in (("cd", SaleCDItem, "cd"), ("tech", SaleTechItem, "tech")):
        for item in model.objects.select_for_update().filter(sale=sale).order_by("pk"):
            existing[(kind, item.pk)] = item
            by_product[(kind, getattr(item, field + "_id"))].append(item)
    old_totals = {key: sum(item.quantity for item in items) for key, items in by_product.items()}
    desired = _product_quantities(prepared)
    all_lines = [{"product_type": key[0], "product_id": key[1], "quantity": max(desired.get(key, 0), old_totals.get(key, 0))}
                 for key in old_totals.keys() | desired.keys()]
    products, stocks = _locked_inventory(sale.warehouse_id, all_lines)
    matched = set()
    for line in prepared:
        key = (line["product_type"], line["product_id"])
        item = None
        if line["item_id"] not in (None, ""):
            try:
                identity = (key[0], int(line["item_id"]))
            except (ValueError, TypeError) as exc:
                raise ValidationError("Некорректный ID строки продажи.") from exc
            item = existing.get(identity)
            if item is None or item not in by_product[key] or identity in matched:
                raise ValidationError("Строка продажи изменена или указана повторно. Обновите форму.")
            matched.add(identity)
        elif line["item_id"] is None:
            # Совместимость вызовов старого API без item_id; новые HTTP-строки передают пустой ID.
            candidates = [value for value in by_product[key] if (key[0], value.pk) not in matched]
            if len(candidates) == 1:
                item = candidates[0]
                matched.add((key[0], item.pk))
            elif len(candidates) > 1:
                raise ValidationError("Для повторных строк при редактировании необходим ID строки.")
        product = products[key]
        if item is None:
            _, _, model, field = _configuration(key[0])
            item = model(sale=sale, **{field: product}, unit_price=_selected_price(product, sale.price_type),
                         product_name_snapshot=product.name, article_snapshot=product.sku, unit_cost_snapshot=product.cost)
        item.quantity, item.unit_discount, item.note = line["quantity"], line["unit_discount"], line["note"]
        if item.unit_discount > item.unit_price:
            raise ValidationError(f"Скидка на товар «{item.product_name_snapshot}» не может превышать цену.")
        item.line_total = ((item.unit_price - item.unit_discount) * item.quantity).quantize(CENT, rounding=ROUND_HALF_UP)
        item.avito_commission_enabled = _commission_enabled(sale_type=sale.sale_type)
        item.avito_commission_amount = calculate_avito_commission(item.line_total, enabled=item.avito_commission_enabled)
        item.full_clean()
        item.save()
    for identity, item in existing.items():
        if identity not in matched:
            item.delete()
    for key in old_totals.keys() | desired.keys():
        delta = desired.get(key, 0) - old_totals.get(key, 0)
        stock = stocks.get(key)
        if stock is None or stock.quantity < delta:
            raise ValidationError(f"На выбранном складе недостаточно товара «{products[key].name}».")
        if not delta:
            continue
        old_quantity = stock.quantity
        stock.quantity -= delta
        stock.full_clean()
        stock.save(update_fields=("quantity",))
        record_product_changes(actor=actor, instance=products[key], source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SALE, action_object_id=sale.pk,
            action_label=f"Продажа {sale.visible_id}",
            changes=[stock_change(warehouse=sale.warehouse, old_quantity=old_quantity, new_quantity=stock.quantity)])
        clear_storage_locations_if_zero(stock=stock, actor=actor, action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk, action_label=f"Продажа {sale.visible_id}")

    SaleCustomItem.objects.filter(sale=sale).delete()
    SaleCustomItem.objects.bulk_create([
        SaleCustomItem(
            sale=sale, system_product_id=line["system_kind"], quantity=line["quantity"], unit_price=line["unit_price"],
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
    if any(line["unit_discount"] for line in prepared + custom_prepared):
        if not resulting_note:
            raise ValidationError("При использовании скидки или доплаты обязательно укажите примечание к продаже.")
    sale.total_amount = total.quantize(CENT, rounding=ROUND_HALF_UP)
    if operation != Sale.OperationKind.NORMAL and sale.total_amount >= Decimal("1e18"):
        raise ValidationError("Сумма системной операции превышает допустимый размер.")
    sale.note = resulting_note
    sale.save(update_fields=("total_amount", "note", "operation_kind", "updated_at", 'partner', 'partner_name_snapshot'))
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


@retry_database_lock
@transaction.atomic
def cancel_sale(*, actor, sale_id, comment, _market=False, restore_stock=True):
    """Возвращает товары и фактическую оплату, сохраняя продажу и все исходные строки."""
    comment = str(comment or "").strip()
    if not comment:
        raise ValidationError("Укажите причину отмены продажи.")
    from orders.arrival import lock_document_trip
    lock_document_trip('sale',sale_id)
    sale = Sale.objects.select_for_update().select_related("warehouse").get(pk=sale_id)
    if not _market and hasattr(sale, "yandex_order"):
        raise ValidationError("Отмените заказ через блок Яндекс Маркета; отправленный товар принимается отдельным возвратом.")
    if not restore_stock and not _market:
        raise ValidationError("Отмена обычной продажи должна восстановить товар.")
    if sale.is_cancelled:
        return SaleCancellationResult(sale=sale, cancelled=False)
    reverse_settlement(sale=sale, actor=actor, comment=comment)
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
            items = [item for item in items if not item.is_direct_delivery]
            locked_items.extend((product_type, product_field, item) for item in items)
            lines.extend({
                "product_type": product_type,
                "product_id": getattr(item, f"{product_field}_id"),
                "quantity": item.quantity,
            } for item in items)
    if not sale.direct_delivery and not lines and not SaleCustomItem.objects.filter(sale=sale).exists():
        if not sale.consignment_items.exists():
            raise ValidationError("В продаже нет товарных позиций для возврата.")
    products, stocks = _locked_inventory(sale.warehouse_id, lines) if lines else ({}, {})

    refund_transaction = None
    refund_amount = Decimal("0.00")
    if sale.payment_status == Sale.PaymentStatus.PAID and sale.operation_kind != Sale.OperationKind.EXPENSE:
        if sale.is_cash_payment:
            if ((sale.cash_received_amount != 0 or sale.debt_offset_amount == 0)
                    and not (sale.procurement_prepaid_amount and sale.cash_received_amount == sale.procurement_prepaid_amount)):
                refund_transaction = refund_sale_payment(
                    sale=sale, actor=actor, comment=f"Отмена {sale.visible_id}: {comment}",
                )
                refund_amount = refund_transaction.amount
        elif sale.is_bank_payment:
            refund_amount = sale.cash_received_amount if sale.cash_received_amount is not None else sale.total_amount

    for product_type, product_field, item in (locked_items if restore_stock else []):
        key = (product_type, getattr(item, f"{product_field}_id"))
        product = products[key]
        if item.unit_cost_snapshot is None:
            raise ValidationError(
                f"Невозможно вернуть «{product.name}»: в старой продаже нет снимка себестоимости."
            )
        stock = stocks.get(key)
        if stock is None:
            _, stock_model, _, _ = _configuration(product_type)
            stock = stock_model(warehouse_id=sale.warehouse_id, **{product_field: product})
        old_quantity = stock.quantity
        old_total_quantity = warehouse_owned_quantity(product_type, product.pk)
        old_cost = product.cost
        product.cost = weighted_warehouse_cost(
            old_quantity=old_total_quantity,
            old_unit_cost=old_cost,
            incoming_quantity=item.quantity,
            incoming_unit_cost=item.unit_cost_snapshot,
        )
        stock.quantity += item.quantity
        stock.full_clean()
        stock.save()
        product.full_clean(exclude=[
            field.name for field in product._meta.fields if field.name != "cost"
        ])
        product.save(update_fields=("cost",))
        changes = [stock_change(
            warehouse=sale.warehouse,
            old_quantity=old_quantity,
            new_quantity=stock.quantity,
        )]
        if old_cost != product.cost:
            changes.append(field_change(
                field_name="cost",
                field_label="Средняя себестоимость на физических складах",
                old_value=f"{old_cost:.2f}",
                new_value=f"{product.cost:.2f}",
            ))
        record_product_changes(
            actor=actor,
            instance=product,
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Отмена продажи {sale.visible_id}",
            changes=changes,
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
