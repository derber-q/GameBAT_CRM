import logging
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from cash.models import CashRegister, CashTransaction
from price.models import ProcurementPriceList, ProcurementPriceListItem
from warehouse.models import Warehouse

from .models import (
    CustomerOrderStatusEvent,
    CustomerProcurementOrder,
    CustomerProcurementOrderItem,
    OrderAdjustment,
    OrderAdjustmentChange,
    SupplierOrderBatch,
    SupplierOrderBatchLine,
)

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


def _new_item(order, source, prepayment, postpayment):
    values = {
        "order": order,
        "price_list_item": source,
        "product_kind": source.product_kind,
        "product_name_snapshot": source.product_name_snapshot,
        "article_snapshot": source.article_snapshot,
        "selected_supplier": source.selected_supplier,
        "supplier_price_aed_snapshot": source.supplier_price_aed,
        "prepayment_unit_price": source.prepayment_price_rub,
        "postpayment_unit_price": source.postpayment_price_rub,
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
def create_customer_procurement_order(*, actor, price_list_id, recipient, comment, lines):
    recipient = str(recipient or "").strip()
    if not recipient:
        raise ValidationError("Получатель обязателен.")
    prepared = _normalise_lines(lines)
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
    order = CustomerProcurementOrder.objects.create(
        recipient=recipient, comment=str(comment or "").strip(), price_list=price_list, created_by=actor
    )
    items = [
        _new_item(order, source_items[item_id], *quantities)
        for item_id, quantities in prepared.items()
    ]
    CustomerProcurementOrderItem.objects.bulk_create(items)
    _save_totals(order, items)
    logger.info(
        "Клиентский закупочный заказ создан: user_id=%s order_id=%s price_list_id=%s items=%s",
        actor.pk, order.pk, price_list.pk, len(items),
    )
    return order


@transaction.atomic
def edit_created_order(*, actor, order_id, recipient, comment, lines):
    prepared = _normalise_lines(lines)
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    if order.status != CustomerProcurementOrder.Status.CREATED:
        raise ValidationError("Изменять состав можно только в статусе «Создан».")
    recipient = str(recipient or "").strip()
    if not recipient:
        raise ValidationError("Получатель обязателен.")
    sources = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.select_for_update().select_related(
            "cd", "tech", "selected_supplier"
        ).filter(price_list=order.price_list, pk__in=prepared)
    }
    if set(sources) != set(prepared):
        raise ValidationError("Товар отсутствует в исходном закупочном прайсе.")
    existing = {
        item.price_list_item_id: item
        for item in CustomerProcurementOrderItem.objects.select_for_update().filter(order=order)
    }
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
    order.save(update_fields=("recipient", "comment", "updated_at"))
    _save_totals(order, list(order.items.all()))
    logger.info("Созданный заказ изменён: user_id=%s order_id=%s", actor.pk, order.pk)
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
    transitions = {
        CustomerProcurementOrder.Status.CREATED: CustomerProcurementOrder.Status.CONFIRMED,
        CustomerProcurementOrder.Status.CONFIRMED: CustomerProcurementOrder.Status.RECEIVING,
        CustomerProcurementOrder.Status.RECEIVING: CustomerProcurementOrder.Status.COMPLETED,
    }
    if transitions.get(order.status) != next_status:
        raise ValidationError("Этот переход статуса недопустим.")
    old_status = order.status
    if next_status == CustomerProcurementOrder.Status.CONFIRMED:
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
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
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
    refund = order.prepayment_total - new_prepayment
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
        if not new_pre and not new_post:
            item.delete()
        elif item.prepayment_quantity != new_pre or item.postpayment_quantity != new_post:
            item.prepayment_quantity = new_pre
            item.postpayment_quantity = new_post
            item.save(update_fields=("prepayment_quantity", "postpayment_quantity"))
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
