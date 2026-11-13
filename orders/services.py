"""Транзакционные переходы клиентских закупочных заказов, их предоплаты/приёмки и связанных записей."""
import logging
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, models

from cash.models import CashRegister, CashTransaction
from price.models import ProcurementPriceList, ProcurementPriceListItem, ProcurementSupplierOffer
from warehouse.models import Warehouse
from catalog.supplier_exclusions import validate_supplier_assignments
from partners.models import Supplier

from .models import (
    CustomerOrderStatusEvent,
    CustomerProcurementOrder,
    CustomerProcurementOrderItem,
    OrderAdjustment,
    OrderAdjustmentChange,
    SupplierOrderBatch,
    SupplierOrderBatchLine,
    SupplierTripAllocation,
)
from .order_editing import require_untransferred_order

logger = logging.getLogger("gamebat.business")
ZERO = Decimal("0.00")


def _quantity(value, label):
    try:
        if isinstance(value, bool) or str(value).strip() == "":
            raise ValueError
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label}: укажите целое количество.") from exc
    if result < 0:
        raise ValidationError(f"{label} не может быть отрицательным.")
    return result


def _normalise_lines(lines):
    result = {}
    for raw in lines:
        try:
            item_id = int(raw.get("price_list_item_id"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Позиция исходного прайса не найдена.") from exc
        if item_id in result:
            raise ValidationError("Товар передан в составе заказа дважды.")
        prepayment = _quantity(raw.get("prepayment_quantity", 0), "Количество предоплаты")
        postpayment = _quantity(raw.get("postpayment_quantity", 0), "Количество постоплаты")
        if prepayment or postpayment:
            result[item_id] = (prepayment, postpayment)
    if not result:
        raise ValidationError("Добавьте хотя бы одну товарную позицию.")
    return result


def _validate_stock_quantities(purpose, quantities):
    if purpose == CustomerProcurementOrder.Purpose.STOCK and any(post for _pre, post in quantities):
        raise ValidationError("Для заказа на склад укажите единое количество без постоплаты.")


def _new_item(order, source, prepayment, postpayment):
    values = {
        "order": order,
        "price_list_item": source,
        "product_kind": source.product_kind,
        "product_name_snapshot": source.product_name_snapshot,
        "article_snapshot": source.article_snapshot,
        "selected_supplier": source.selected_supplier,
        "supplier_price_aed_snapshot": source.supplier_price_aed,
        "prepayment_unit_price": source.stock_unit_cost if order.is_stock_order else source.prepayment_price_rub,
        "postpayment_unit_price": source.stock_unit_cost if order.is_stock_order else source.postpayment_price_rub,
        "prepayment_quantity": prepayment,
        "postpayment_quantity": postpayment,
        source.product_kind: source.product,
    }
    return CustomerProcurementOrderItem(**values)


def _totals(items):
    prepayment = sum((item.prepayment_line_total for item in items), ZERO)
    postpayment = sum((item.postpayment_line_total for item in items), ZERO)
    return prepayment, postpayment, prepayment + postpayment


def _save_totals(order, items):
    prepayment, postpayment, grand = _totals(items)
    order.prepayment_total = prepayment
    order.postpayment_total = postpayment
    order.grand_total = grand
    order.full_clean()
    order.save(update_fields=("prepayment_total", "postpayment_total", "grand_total", "updated_at"))


@transaction.atomic
def create_customer_procurement_order(*, actor, price_list_id, recipient, comment, lines,
                                     purpose=CustomerProcurementOrder.Purpose.CUSTOMER, partner_id=None, partner_name=''):
    from partners.customers import resolve_customer
    partner, customer_name = resolve_customer(partner_id=partner_id, partner_name=partner_name)
    if purpose == CustomerProcurementOrder.Purpose.STOCK and customer_name:
        raise ValidationError('Заказ на склад не привязывается к заказчику.')
    if purpose not in CustomerProcurementOrder.Purpose.values:
        raise ValidationError("Неизвестное назначение заказа.")
    if purpose == CustomerProcurementOrder.Purpose.STOCK and not actor.has_perm("price.view_supplier_prices"):
        raise PermissionDenied("Для заказа на склад требуется право просмотра закупочных цен.")
    recipient = str(recipient or "").strip()
    if purpose == CustomerProcurementOrder.Purpose.STOCK and not recipient:
        recipient = "На склад"
    if not recipient:
        raise ValidationError("Получатель обязателен.")
    prepared = _normalise_lines(lines)
    _validate_stock_quantities(purpose, prepared.values())
    try:
        price_list = ProcurementPriceList.objects.select_for_update().get(pk=price_list_id)
    except ProcurementPriceList.DoesNotExist as exc:
        raise ValidationError("Исходный закупочный прайс не найден.") from exc
    source_items = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.select_for_update().select_related(
            "cd", "tech", "selected_supplier"
        ).filter(price_list=price_list, pk__in=prepared)
    }
    if set(source_items) != set(prepared):
        raise ValidationError("Одна из позиций отсутствует в исходном закупочном прайсе.")
    if any(item.product.is_archived for item in source_items.values()):
        raise ValidationError("Удалённый товар нельзя включить в новый заказ.")
    validate_supplier_assignments((item.product_kind, item.product_id, item.selected_supplier_id, item.product_name_snapshot) for item in source_items.values())
    order = CustomerProcurementOrder.objects.create(
        recipient=recipient, comment=str(comment or "").strip(), price_list=price_list, created_by=actor,
        purpose=purpose,
        partner=partner, partner_name_snapshot=customer_name or (recipient if purpose == CustomerProcurementOrder.Purpose.CUSTOMER else ''),
    )
    items = [
        _new_item(order, source_items[item_id], *quantities)
        for item_id, quantities in prepared.items()
    ]
    CustomerProcurementOrderItem.objects.bulk_create(items)
    _save_totals(order, items)
    logger.info(
        "Закупочный заказ создан: user_id=%s order_id=%s price_list_id=%s items=%s purpose=%s",
        actor.pk, order.pk, price_list.pk, len(items), purpose,
    )
    return order


def _edit_unassigned_order(*, actor, order, recipient, comment, prepared,
                           partner_id=None, partner_name=None):
    require_untransferred_order(order)
    if order.status != CustomerProcurementOrder.Status.CREATED:
        raise ValidationError("Изменять состав можно только в статусе «Создан».")
    if order.trip_id:
        raise ValidationError("Заказ уже добавлен в рейс. Обновите страницу и повторите изменение.")
    if (partner_name is not None or partner_id is not None) and not (
            partner_id is not None and str(partner_id) == str(order.partner_id) and not partner_name):
        from partners.customers import resolve_customer
        partner, name = resolve_customer(partner_id=partner_id, partner_name=partner_name or '')
        if order.is_stock_order and name:
            raise ValidationError('Заказ на склад не привязывается к заказчику.')
        order.partner = partner
        order.partner_name_snapshot = name or (recipient if not order.is_stock_order else '')
    _validate_stock_quantities(order.purpose, prepared.values())
    recipient = str(recipient or "").strip()
    if not recipient:
        raise ValidationError("Получатель обязателен.")
    existing = {
        item.price_list_item_id: item
        for item in CustomerProcurementOrderItem.objects.select_for_update().filter(order=order)
    }
    sources = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.select_for_update().select_related(
            "cd", "tech", "selected_supplier"
        ).filter(pk__in=prepared).filter(
            models.Q(price_list=order.price_list) | models.Q(pk__in=existing)
        )
    }
    if set(sources) != set(prepared):
        raise ValidationError("Товар отсутствует в исходном закупочном прайсе.")
    if any(item.product.is_archived for item in sources.values()):
        raise ValidationError("Удалённый товар нельзя включить в заказ.")
    validate_supplier_assignments(
        (sources[key].product_kind, sources[key].product_id, sources[key].selected_supplier_id, sources[key].product_name_snapshot)
        for key, quantities in prepared.items()
        if key not in existing or sum(quantities) > existing[key].prepayment_quantity + existing[key].postpayment_quantity
    )
    for source_id, item in list(existing.items()):
        quantities = prepared.get(source_id)
        if quantities is None:
            item.delete()
            continue
        item.prepayment_quantity, item.postpayment_quantity = quantities
        item.full_clean()
        item.save(update_fields=("prepayment_quantity", "postpayment_quantity"))
    for source_id, quantities in prepared.items():
        if source_id not in existing:
            item = _new_item(order, sources[source_id], *quantities)
            item.full_clean()
            item.save()
    order.recipient = recipient
    order.comment = str(comment or "").strip()
    order.save(update_fields=("recipient", "comment", "updated_at", "partner", "partner_name_snapshot"))
    _save_totals(order, list(order.items.all()))
    logger.info("Созданный заказ изменён: user_id=%s order_id=%s", actor.pk, order.pk)
    return order


@transaction.atomic
def edit_created_order(*, actor, order_id, recipient, comment, lines, partner_id=None,
                       partner_name=None, revision=None):
    prepared = _normalise_lines(lines)
    reference = CustomerProcurementOrder.objects.filter(pk=order_id).values("trip_id").first()
    if reference is None:
        raise ValidationError("Заказ не найден.")
    if reference["trip_id"]:
        from .trips import edit_trip_order_composition
        return edit_trip_order_composition(
            actor=actor, order_id=order_id, revision=revision, recipient=recipient,
            comment=comment, prepared=prepared,
        )
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    return _edit_unassigned_order(actor=actor, order=order, recipient=recipient, comment=comment,
                                  prepared=prepared, partner_id=partner_id, partner_name=partner_name)


def _normalise_additions(lines):
    result = {}
    for raw in lines:
        try:
            item_id = int(raw.get("price_list_item_id"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Позиция исходного прайса не найдена.") from exc
        if item_id in result:
            raise ValidationError("Товар передан в составе заказа дважды.")
        quantity = _quantity(raw.get("quantity", 0), "Количество к добавлению")
        if quantity > 2147483647:
            raise ValidationError("Слишком большое количество к добавлению.")
        if quantity:
            result[item_id] = quantity
    if not result:
        raise ValidationError("Укажите количество хотя бы для одного товара.")
    return result


@transaction.atomic
def add_items_to_order(*, actor, order_id, lines, revision=None):
    additions = _normalise_additions(lines)
    reference = CustomerProcurementOrder.objects.filter(pk=order_id).values("trip_id").first()
    if reference is None:
        raise ValidationError("Заказ не найден.")
    if reference["trip_id"]:
        from .trips import add_items_to_trip_order
        return add_items_to_trip_order(actor=actor, order_id=order_id, lines=additions, revision=revision)
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    require_untransferred_order(order)
    if order.status != CustomerProcurementOrder.Status.CREATED or order.trip_id:
        raise ValidationError("Дополнительные товары можно добавить только в созданный заказ без рейса.")
    sources = {
        item.pk: item for item in ProcurementPriceListItem.objects.select_for_update().select_related(
            "cd", "tech", "selected_supplier"
        ).filter(price_list=order.price_list, pk__in=additions)
    }
    if set(sources) != set(additions) or any(source.product.is_archived for source in sources.values()):
        raise ValidationError("Выбранный товар отсутствует в прайсе или архивирован.")
    current = {item.price_list_item_id: item for item in order.items.select_for_update().all()}
    prepared = {source_id: (item.prepayment_quantity, item.postpayment_quantity)
                for source_id, item in current.items()}
    for source_id, quantity in additions.items():
        pre, post = prepared.get(source_id, (0, 0))
        prepared[source_id] = (pre + quantity, post) if order.is_stock_order else (pre, post + quantity)
        if sum(prepared[source_id]) > 2147483647:
            raise ValidationError("Итоговое количество товара слишком велико.")
    return _edit_unassigned_order(actor=actor, order=order, recipient=order.recipient,
        comment=order.comment, prepared=prepared, partner_id=None, partner_name=None)


@transaction.atomic
def add_catalog_items_to_order(*, actor, order_id, lines, revision=None):
    """Оформляет новые каталожные позиции сразу в выбранный заказ без распределения по клиентам."""
    if not actor.has_perms(("orders.edit_created_order", "price.view_supplier_prices", "partners.view_supplier_details")):
        raise PermissionDenied("Недостаточно прав для добавления товаров с закупочными ценами.")
    from catalog.models import CD, Tech
    from price.services import decimal_value, procurement_delivery
    from .trip_prices import validated_aed
    from .models import SupplierTripAllocation

    order_ref = CustomerProcurementOrder.objects.filter(pk=order_id).values("trip_id").first()
    if order_ref is None:
        raise ValidationError("Заказ не найден.")
    batch = None
    if order_ref["trip_id"]:
        from .trips import (
            _assert_balances, _line_for, _record_customer_changes, _record_trip_change,
            _require_editable_trip, _require_manage,
        )
        _require_manage(actor)
        batch = SupplierOrderBatch.objects.select_for_update().select_related("price_list").get(
            pk=order_ref["trip_id"]
        )
        if batch.revision != _quantity(revision, "Версия рейса"):
            raise ValidationError("Рейс уже изменён другим запросом. Обновите страницу.")
        _require_editable_trip(batch)
        _assert_balances(batch)
    order = CustomerProcurementOrder.objects.select_for_update().select_related(
        "price_list", "trip", "trip__price_list"
    ).get(pk=order_id)
    require_untransferred_order(order)
    if order.status != CustomerProcurementOrder.Status.CREATED:
        raise ValidationError("Дополнительные товары можно добавить только в заказе со статусом «Создан».")
    if order.trip_id != order_ref["trip_id"]:
        raise ValidationError("Заказ переместили в другой рейс. Обновите страницу.")
    if batch:
        calculation_price_list = batch.price_list or order.price_list
        accepted_suppliers = set(batch.invoice_flags.filter(accepted=True).values_list("supplier_id", flat=True))
    else:
        calculation_price_list = order.price_list
        accepted_suppliers = set()
    if not lines or len(lines) > 100:
        raise ValidationError("Укажите от 1 до 100 дополнительных товаров.")

    models_by_kind = {"cd": CD, "tech": Tech}
    normalized, seen = [], set()
    for raw in lines:
        try:
            kind, product_id = str(raw.get("product", "")).split(":", 1)
            product_model = models_by_kind[kind]
            product = product_model.objects.active().get(pk=int(product_id))
            supplier = Supplier.objects.get(pk=int(raw.get("supplier")))
        except (KeyError, ValueError, TypeError, CD.DoesNotExist, Tech.DoesNotExist, Supplier.DoesNotExist) as exc:
            raise ValidationError("Выберите действующий товар и поставщика.") from exc
        if (kind, product.pk) in seen:
            raise ValidationError("Один товар нельзя добавить дважды в одной форме.")
        seen.add((kind, product.pk))
        if CustomerProcurementOrderItem.objects.filter(order=order, product_kind=kind,
                                                        **{f"{kind}_id": product.pk}).exists():
            raise ValidationError(f"{product.name} уже есть в заказе. Измените его количество в составе заказа.")
        aed = validated_aed(raw.get("supplier_price_aed"))
        customer_price = None if order.is_stock_order else decimal_value(
            raw.get("customer_price"), nonnegative=True, label="Цена заказчика")
        quantity = _quantity(raw.get("quantity"), "Количество")
        if not quantity or quantity > 2147483647:
            raise ValidationError(f"{product.name}: укажите положительное количество.")
        if batch and supplier.pk in accepted_suppliers:
            raise ValidationError(f"Инвойс поставщика {supplier.name} уже принят. Снимите отметку на странице рейса.")
        validate_supplier_assignments([(kind, product.pk, supplier.pk, product.name)])
        delivery, group, tariff = procurement_delivery(
            product=product, kind=kind, price_list=calculation_price_list,
        )
        base = decimal_value(aed * calculation_price_list.exchange_rate_aed_rub,
                             nonnegative=True, label="Закупочная база")
        cost = base + delivery
        if order.is_stock_order:
            customer_price = cost
        normalized.append({"kind": kind, "product": product, "supplier": supplier, "aed": aed,
            "customer_price": customer_price, "quantity": quantity, "delivery": delivery,
            "group": group, "tariff": tariff, "base": base, "cost": cost})

    fixed_fields = (
        "exchange_rate_usdt_aed", "exchange_rate_usdt_rub", "exchange_rate_aed_rub",
        "delivery_general_usdt_per_kg", "delivery_devices_usdt_per_kg",
        "delivery_storage_usdt_per_kg", "delivery_cd_rub",
    )
    source_list = ProcurementPriceList.objects.create(
        created_by=actor, supplier_offers_complete=True, is_trip_addition=True,
        **{field: getattr(calculation_price_list, field) for field in fixed_fields},
    )
    created_items, adjustment_changes, trip_changes = [], [], []
    for row in normalized:
        kind, product = row["kind"], row["product"]
        markup = row["customer_price"] - row["cost"]
        customer_price = row["customer_price"]
        source = ProcurementPriceListItem.objects.create(
            price_list=source_list, product_kind=kind, **{kind: product},
            product_name_snapshot=product.name, article_snapshot=product.sku,
            selected_supplier=row["supplier"], supplier_price_aed=row["aed"],
            exchange_rate_aed_rub=calculation_price_list.exchange_rate_aed_rub,
            base_price_rub=row["base"], markup_rub=markup, original_markup_rub=markup,
            delivery_rub=row["delivery"], weight_grams_snapshot=product.weight_grams,
            delivery_group_snapshot=row["group"], delivery_usdt_per_kg_snapshot=row["tariff"],
            prepayment_price_rub=customer_price, postpayment_price_rub=customer_price,
            postpayment_surcharge_rub=0,
        )
        ProcurementSupplierOffer.objects.create(
            price_list_item=source, supplier=row["supplier"], price_aed=row["aed"],
        )
        item = _new_item(order, source,
            row["quantity"] if order.is_stock_order else 0,
            0 if order.is_stock_order else row["quantity"])
        item.full_clean()
        item.save()
        created_items.append(item)
        adjustment_changes.append((item,
            "prepayment_quantity" if order.is_stock_order else "postpayment_quantity",
            0, row["quantity"]))
        if batch:
            line = _line_for(batch, source, row["supplier"].pk, row["supplier"].pk, row["aed"])
            if line.quantity + row["quantity"] > 2147483647:
                raise ValidationError("Слишком большое количество в строке поставщика.")
            line.quantity += row["quantity"]
            line.save(update_fields=("quantity",))
            allocation = SupplierTripAllocation.objects.create(
                line=line, order_item=item,
                prepayment_quantity=row["quantity"] if order.is_stock_order else 0,
                postpayment_quantity=0 if order.is_stock_order else row["quantity"],
                prepayment_cap=row["quantity"] if order.is_stock_order else 0,
            )
            trip_changes.append({"item_id": item.pk, "line_id": line.pk,
                "supplier_id": line.supplier_id, "quantity": allocation.quantity,
                "name": item.product_name_snapshot})

    _save_totals(order, list(order.items.all()))
    if batch:
        _record_customer_changes(actor, {order.pk: adjustment_changes}, batch,
            comment=f"Добавлены дополнительные товары в заказ в рейсе №{batch.pk}.")
        _record_trip_change(batch, actor, f"Добавлены товары в заказ №{order.pk}", {
            "action": "add_catalog_items_to_order", "order_id": order.pk, "items": trip_changes,
            "price_list_id": source_list.pk,
        })
        _assert_balances(batch)
    else:
        adjustment = OrderAdjustment.objects.create(order=order, actor=actor,
            comment="Добавлены дополнительные товары из каталога.", refund_amount=0)
        OrderAdjustmentChange.objects.bulk_create([
            OrderAdjustmentChange(adjustment=adjustment, product_kind=item.product_kind,
                product_id_snapshot=item.product_id, product_name_snapshot=item.product_name_snapshot,
                field_name=field, old_value=old, new_value=new)
            for item, field, old, new in adjustment_changes if old != new
        ])
    logger.info("В заказ добавлены каталожные позиции: user_id=%s order_id=%s count=%s",
                actor.pk, order.pk, len(created_items))
    return order


def _locked_register(warehouse_id):
    try:
        return CashRegister.objects.select_for_update().select_related("warehouse").get(warehouse_id=warehouse_id)
    except CashRegister.DoesNotExist as exc:
        raise ValidationError("Для выбранного склада не создана касса.") from exc


def _select_payment_warehouse(order, warehouse_id, *, required):
    if order.payment_warehouse_id:
        if warehouse_id and int(warehouse_id) != order.payment_warehouse_id:
            raise ValidationError("Склад оплаты уже зафиксирован и не может быть изменён.")
        return order.payment_warehouse_id
    if not warehouse_id:
        if required:
            raise ValidationError("Выберите склад для денежной операции.")
        return None
    try:
        warehouse_id = int(warehouse_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    if not Warehouse.objects.filter(pk=warehouse_id).exists():
        raise ValidationError("Выберите существующий склад.")
    order.payment_warehouse_id = warehouse_id
    return warehouse_id


def _status_event(order, actor, old_status, new_status):
    CustomerOrderStatusEvent.objects.create(
        order=order, actor=actor, old_status=old_status, new_status=new_status
    )


@transaction.atomic
def advance_order_status(*, actor, order_id, next_status, warehouse_id=None):
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    if order.trip_id and order.total_units and next_status == order.Status.COMPLETED:
        raise ValidationError('Заказ рейса выполняется через связанную продажу или приход. Сначала создайте операцию с указанием курсов.')
    if order.is_stock_order and next_status == order.Status.COMPLETED:
        return receive_stock_order(actor=actor, order_id=order.pk, warehouse_id=warehouse_id)
    require_untransferred_order(order)
    transitions = {
        CustomerProcurementOrder.Status.CREATED: CustomerProcurementOrder.Status.CONFIRMED,
        CustomerProcurementOrder.Status.CONFIRMED: CustomerProcurementOrder.Status.RECEIVING,
        CustomerProcurementOrder.Status.RECEIVING: CustomerProcurementOrder.Status.COMPLETED,
    }
    if transitions.get(order.status) != next_status:
        raise ValidationError("Этот переход статуса недопустим.")
    old_status = order.status
    if next_status == CustomerProcurementOrder.Status.CONFIRMED and not order.is_stock_order:
        selected = _select_payment_warehouse(order, warehouse_id, required=order.prepayment_total > 0)
        if order.prepayment_total > 0:
            register = _locked_register(selected)
            if CashTransaction.objects.select_for_update().filter(
                customer_order=order, operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_PREPAYMENT
            ).exists():
                raise ValidationError("Предоплата этого заказа уже проведена.")
            register.balance += order.prepayment_total
            register.full_clean()
            register.save(update_fields=("balance",))
            CashTransaction.objects.create(
                cash_register=register, customer_order=order,
                operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_PREPAYMENT,
                amount=order.prepayment_total, comment=f"Предоплата по заказу №{order.pk}.", created_by=actor,
            )
    elif next_status == CustomerProcurementOrder.Status.COMPLETED:
        selected = _select_payment_warehouse(order, warehouse_id, required=order.postpayment_total > 0)
        if order.postpayment_total > 0:
            register = _locked_register(selected)
            if CashTransaction.objects.select_for_update().filter(
                customer_order=order, operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_POSTPAYMENT
            ).exists():
                raise ValidationError("Постоплата этого заказа уже проведена.")
            register.balance += order.postpayment_total
            register.full_clean()
            register.save(update_fields=("balance",))
            CashTransaction.objects.create(
                cash_register=register, customer_order=order,
                operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_POSTPAYMENT,
                amount=order.postpayment_total, comment=f"Постоплата по заказу №{order.pk}.", created_by=actor,
            )
    order.status = next_status
    order.save(update_fields=("status", "payment_warehouse", "updated_at"))
    _status_event(order, actor, old_status, next_status)
    logger.info(
        "Статус закупочного заказа изменён: user_id=%s order_id=%s status=%s",
        actor.pk, order.pk, next_status,
    )
    return order


@transaction.atomic
def reduce_receiving_order(*, actor, order_id, comment, rows, allow_refund=True):
    comment = str(comment or "").strip()
    if not comment:
        raise ValidationError("Комментарий к корректировке обязателен.")
    # Порядок блокировок совпадает с редактированием рейса: сначала рейс, затем заказ.
    trip_id = CustomerProcurementOrder.objects.filter(pk=order_id).values_list('trip_id', flat=True).first()
    batch = SupplierOrderBatch.objects.select_for_update().get(pk=trip_id) if trip_id else None
    if batch:
        from .trips import _assert_balances
        _assert_balances(batch)
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    require_untransferred_order(order)
    if order.status != CustomerProcurementOrder.Status.RECEIVING:
        raise ValidationError("Корректировка доступна только в статусе «Принимается».")
    existing = {
        item.pk: item
        for item in CustomerProcurementOrderItem.objects.select_for_update().filter(order=order)
    }
    parsed = {}
    for raw in rows:
        try:
            item_id = int(raw.get("item_id"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Позиция заказа не найдена.") from exc
        if item_id in parsed:
            raise ValidationError("Позиция заказа передана дважды.")
        parsed[item_id] = (
            _quantity(raw.get("prepayment_quantity"), "Количество предоплаты"),
            _quantity(raw.get("postpayment_quantity"), "Количество постоплаты"),
        )
    if set(parsed) != set(existing):
        raise ValidationError("Нельзя добавлять или скрывать позиции при приёмке.")
    changes = []
    for item_id, item in existing.items():
        new_pre, new_post = parsed[item_id]
        if batch:
            # При частичной приёмке сохраняем первые партии; уменьшаем последние,
            # не оставляя лишние доли рейса с прежним количеством заказа.
            allocations = list(item.trip_allocations.select_for_update().filter(line__batch=batch).order_by('-line_id', '-pk'))
            for field, desired in (('prepayment_quantity', new_pre), ('postpayment_quantity', new_post)):
                remaining = getattr(item, field) - desired
                for allocation in allocations:
                    removed = min(remaining, getattr(allocation, field))
                    if not removed:
                        continue
                    line = SupplierOrderBatchLine.objects.select_for_update().get(pk=allocation.line_id)
                    setattr(allocation, field, getattr(allocation, field) - removed)
                    allocation.save(update_fields=(field,))
                    line.quantity -= removed
                    line.save(update_fields=('quantity',))
                    remaining -= removed
                if remaining:
                    raise ValidationError('Распределение рейса не покрывает корректируемое количество.')
        if new_pre > item.prepayment_quantity or new_post > item.postpayment_quantity:
            raise ValidationError(f"Нельзя увеличить количество товара «{item.product_name_snapshot}».")
        for field, old_value, new_value in (
            ("prepayment_quantity", item.prepayment_quantity, new_pre),
            ("postpayment_quantity", item.postpayment_quantity, new_post),
        ):
            if old_value != new_value:
                changes.append((item, field, old_value, new_value))
    if not changes:
        raise ValidationError("Состав заказа не изменён.")
    new_prepayment = sum(
        (item.prepayment_unit_price * parsed[item_id][0] for item_id, item in existing.items()), ZERO
    )
    new_postpayment = sum(
        (item.postpayment_unit_price * parsed[item_id][1] for item_id, item in existing.items()), ZERO
    )
    new_grand = new_prepayment + new_postpayment
    refund = ZERO if order.is_stock_order else order.prepayment_total - new_prepayment
    if refund > 0 and not allow_refund:
        raise ValidationError("Для возврата требуется право на расходную операцию кассы.")
    register = None
    if refund > 0:
        if not order.payment_warehouse_id:
            raise ValidationError("Для заказа не зафиксирован склад оплаты.")
        register = _locked_register(order.payment_warehouse_id)
        if register.balance < refund:
            raise ValidationError("В кассе недостаточно наличных для возврата заказчику.")
    adjustment = OrderAdjustment.objects.create(
        order=order, actor=actor, comment=comment, refund_amount=refund
    )
    OrderAdjustmentChange.objects.bulk_create([
        OrderAdjustmentChange(
            adjustment=adjustment, product_kind=item.product_kind,
            product_id_snapshot=item.product_id, product_name_snapshot=item.product_name_snapshot,
            field_name=field, old_value=old_value, new_value=new_value,
        )
        for item, field, old_value, new_value in changes
    ])
    for item_id, item in existing.items():
        new_pre, new_post = parsed[item_id]
        if not new_pre and not new_post and not item.trip_allocations.exists():
            item.delete()
        elif item.prepayment_quantity != new_pre or item.postpayment_quantity != new_post:
            item.prepayment_quantity = new_pre
            item.postpayment_quantity = new_post
            item.save(update_fields=("prepayment_quantity", "postpayment_quantity"))
    if batch:
        from .trips import _assert_balances, _record_trip_change
        _assert_balances(batch)
        _record_trip_change(batch, actor, f'Частичная приёмка заказа №{order.pk}: обновлено распределение рейса.',
                            {'action': 'receiving_reduction', 'order_id': order.pk, 'adjustment_id': adjustment.pk})
    if refund > 0:
        register.balance -= refund
        register.full_clean()
        register.save(update_fields=("balance",))
        CashTransaction.objects.create(
            cash_register=register, customer_order=order, order_adjustment=adjustment,
            operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_REFUND,
            amount=refund, comment=f"Возврат по заказу №{order.pk}. {comment}", created_by=actor,
        )
    order.prepayment_total = new_prepayment
    order.postpayment_total = new_postpayment
    order.grand_total = new_grand
    order.save(update_fields=("prepayment_total", "postpayment_total", "grand_total", "updated_at"))
    logger.info(
        "Закупочный заказ скорректирован: user_id=%s order_id=%s adjustment_id=%s refund=%s",
        actor.pk, order.pk, adjustment.pk, refund,
    )
    return adjustment


@transaction.atomic
def receive_stock_order(*, actor, order_id, warehouse_id):
    """Создать один приход по доставленному заказу, сохранив исходную стоимость."""
    from supplies.services import accept_supply
    from .trip_prices import allocation_unit_cost

    if not (actor.has_perm("orders.complete_order") and actor.has_perm("supplies.add_supply")
            and actor.has_perm("price.view_supplier_prices")):
        raise PermissionDenied("Для оформления прихода требуются права выполнения заказа, приёмки и просмотра закупочных цен.")
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    if not order.is_stock_order:
        raise ValidationError("Приход оформляется только для заказа на склад.")
    if order.trip_id:
        raise ValidationError('Подтвердите прибытие рейса и создайте отдельный приход из его заказа для общей финализации.')
    if order.supply_id:
        return order
    if order.status != order.Status.RECEIVING:
        raise ValidationError("Приход доступен только после начала приёмки заказа.")
    lines = []
    for item in order.items.select_for_update().order_by("pk"):
        remaining = item.quantity
        if not remaining:
            continue
        # Получатель закупки может меняться в рейсе; стоимость остаётся снимком заказа.
        allocations = item.trip_allocations.select_related("line").order_by("line_id") if order.trip_id else ()
        for allocation in allocations:
            amount = min(remaining, allocation.quantity)
            if amount:
                lines.append({
                    "product_type": item.product_kind, "product_id": item.product_id,
                    "supplier_id": allocation.line.supplier_id, "quantity": amount,
                    "purchase_unit_cost": allocation_unit_cost(item, allocation.line, for_supply=True),
                })
                remaining -= amount
        if remaining and order.trip_id:
            raise ValidationError("Количество заказа превышает распределение в рейсе.")
        if remaining:
            lines.append({
                "product_type": item.product_kind, "product_id": item.product_id,
                "supplier_id": item.selected_supplier_id, "quantity": remaining,
                "purchase_unit_cost": item.prepayment_unit_price,
            })
    supply = accept_supply(accepted_by=actor, warehouse_id=warehouse_id, lines=lines, defer_balance=True)
    order.supply = supply
    order.status = order.Status.COMPLETED
    order.save(update_fields=("supply", "status", "updated_at"))
    _status_event(order, actor, order.Status.RECEIVING, order.Status.COMPLETED)
    logger.info("Приход по заказу на склад создан: user_id=%s order_id=%s supply_id=%s",
                actor.pk, order.pk, supply.pk)
    return order


@transaction.atomic
def create_supplier_order_batch(*, actor, order_ids):
    try:
        ids = {int(value) for value in order_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError("Выберите существующие клиентские заказы.") from exc
    if not ids:
        raise ValidationError("Выберите хотя бы один клиентский заказ.")
    orders = list(CustomerProcurementOrder.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    if len(orders) != len(ids):
        raise ValidationError("Один из выбранных заказов не найден.")
    items = CustomerProcurementOrderItem.objects.select_for_update().select_related(
        "cd", "tech", "selected_supplier"
    ).filter(order_id__in=ids).order_by("order_id", "id")
    aggregated = {}
    for item in items:
        quantity = item.prepayment_quantity + item.postpayment_quantity
        if not quantity:
            continue
        if item.product.is_archived:
            raise ValidationError("Удалённый товар нельзя включить в новый заказ поставщику.")
        key = (item.selected_supplier_id, item.product_kind, item.product_id)
        if key not in aggregated:
            aggregated[key] = {
                "item": item, "quantity": 0,
                "supplier_cost_total": ZERO,
            }
        aggregated[key]["quantity"] += quantity
        aggregated[key]["supplier_cost_total"] += item.supplier_price_aed_snapshot * quantity
    if not aggregated:
        raise ValidationError("В выбранных заказах нет товарных позиций.")
    validate_supplier_assignments((data['item'].product_kind, data['item'].product_id, supplier_id, data['item'].product_name_snapshot)
                                  for (supplier_id, _kind, _pk), data in aggregated.items())
    batch = SupplierOrderBatch.objects.create(created_by=actor)
    batch.source_orders.set(orders)
    lines = []
    for (supplier_id, kind, _), data in aggregated.items():
        item = data["item"]
        values = {
            "batch": batch, "supplier_id": supplier_id, "product_kind": kind,
            "product_name_snapshot": item.product_name_snapshot,
            "article_snapshot": item.article_snapshot,
            "quantity": data["quantity"],
            "supplier_price_aed_snapshot": (
                data["supplier_cost_total"] / data["quantity"]
            ).quantize(Decimal("0.000001")),
            kind: item.product,
        }
        lines.append(SupplierOrderBatchLine(**values))
    SupplierOrderBatchLine.objects.bulk_create(lines)
    logger.info(
        "Подборка заказов поставщикам создана: user_id=%s batch_id=%s orders=%s lines=%s",
        actor.pk, batch.pk, len(orders), len(lines),
    )
    return batch


@transaction.atomic
def delete_unassigned_order(*, actor, order_id):
    """Удаляет только чистый созданный заказ, не связанный с рейсом или денежной историей."""
    if not (actor.is_superuser or actor.has_perm("orders.edit_created_order")):
        raise PermissionDenied("Недостаточно прав для удаления заказа.")
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ уже удалён или не найден.") from exc
    if order.is_stock_order and not actor.has_perm("price.view_supplier_prices"):
        raise PermissionDenied("Для удаления заказа на склад требуется доступ к закупочным ценам.")
    if order.trip_id or order.status != CustomerProcurementOrder.Status.CREATED:
        raise ValidationError("Удалять можно только созданный заказ, который не включён в рейс.")
    if (order.supply_id or order.operations.exists() or order.cash_transactions.exists()
            or order.status_events.exists() or order.adjustments.exists()
            or order.supplier_order_batches.exists() or order.tripadditionreceipt_set.exists()):
        raise ValidationError("У заказа есть связанная операция или история. Удаление недоступно.")
    items = list(CustomerProcurementOrderItem.objects.select_for_update().filter(order=order))
    item_ids = [item.pk for item in items]
    if (SupplierTripAllocation.objects.filter(order_item_id__in=item_ids).exists()
            or any(item.arrival_rows.exists() for item in items)):
        raise ValidationError("Заказ уже участвовал в учёте рейса. Удаление недоступно.")
    CustomerProcurementOrderItem.objects.filter(order=order).delete()
    order_id = order.pk
    order.delete()
    logger.info("Черновой заказ без рейса удалён: user_id=%s order_id=%s", actor.pk, order_id)
    return order_id
