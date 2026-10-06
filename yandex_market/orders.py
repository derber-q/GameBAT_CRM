"""Снимки внешнего заказа и штатные продажи; доставка, оплата и возврат независимы."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from sales.models import Sale
from sales.services import advance_order_status, cancel_sale, create_sale
from warehouse.receipts import receive_return
from .models import AuditEvent, OfferConnection, OrderLine, OrderMetadata, ReturnMetadata

SHIPPED = {"DELIVERY", "PICKUP", "DELIVERED", "PARTIALLY_RETURNED", "RETURNED"}
AFTER_SHIPMENT_CANCELLATIONS = {
    "USER_REFUSED_DELIVERY", "USER_REFUSED_PRODUCT", "USER_REFUSED_QUALITY", "PICKUP_EXPIRED",
    "DELIVERY_SERVICE_UNDELIVERED", "DELIVERY_SERVICE_LOST", "DELIVERY_SERVICE_NOT_RECEIVED",
    "SHIPPED_TO_WRONG_DELIVERY_SERVICE", "SORTING_CENTER_LOST", "DROPOFF_LOST", "LOST",
    "FULL_NOT_RANSOM", "DAMAGED_BOX", "WRONG_ITEM_DELIVERED", "COURIER_RETURNED_ORDER",
}
STATUS_MAP = {
    ("PROCESSING", "STARTED"): Sale.OrderStatus.CREATED,
    ("PROCESSING", "READY_TO_SHIP"): Sale.OrderStatus.ASSEMBLED,
    ("DELIVERY", ""): Sale.OrderStatus.SHIPPED,
    ("PICKUP", ""): Sale.OrderStatus.SHIPPED,
    ("DELIVERED", ""): Sale.OrderStatus.DELIVERED,
}


def aware_date(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise ValidationError("Дата Маркета не содержит корректного часового пояса.")
    return parsed


def item_amount(item):
    prices = item.get("prices", {})
    payment = prices.get("payment")
    if not payment:
        raise ValidationError("В заказе Маркета отсутствует стоимость строки.")
    total = Decimal("0")
    # В актуальном API payment/cashback относятся ко ВСЕМ единицам строки.
    # Subsidy — отдельное вознаграждение; формулу статистики им не меняем.
    for price in (payment, prices.get("cashback", {"value": 0, "currencyId": "RUR"})):
        if price.get("currencyId") != "RUR":
            raise ValidationError("Импорт поддерживает заказы в рублях.")
        try:
            amount = Decimal(str(price["value"]))
        except (InvalidOperation, KeyError, ValueError) as exc:
            raise ValidationError("Некорректная стоимость строки Маркета.") from exc
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValidationError("Некорректная стоимость строки Маркета.")
        total += amount
    return total


def available_actions(order):
    if order.status == "PROCESSING" and order.substatus == "STARTED":
        return {"ready": "Готов к отгрузке", "cancel": "Отменить: магазин не может выполнить заказ"}
    if order.status == "PROCESSING" and order.substatus == "READY_TO_SHIP":
        return {"cancel": "Отменить: магазин не может выполнить заказ"}
    return {}


def action_payload(order, action):
    if action not in available_actions(order):
        raise ValidationError("Действие недоступно для текущего статуса Маркета.")
    if action == "ready":
        if not order.sale_id or not order.boxes:
            raise ValidationError("Сначала создайте продажу и передайте состав коробок.")
        return {"order": {"status": "PROCESSING", "substatus": "READY_TO_SHIP"}}
    return {"order": {"status": "CANCELLED", "substatus": "SHOP_FAILED"}}


def import_order(integration, payload):
    if payload.get("campaignId") != integration.campaign_id or payload.get("programType", "FBS") != "FBS":
        raise ValidationError("Заказ относится к другому магазину или модели работы.")
    order, _ = OrderMetadata.objects.get_or_create(integration=integration, order_id=int(payload["orderId"]))
    try:
        return _apply_order(order.pk, payload)
    except ValidationError as exc:
        values = {"last_error": " ".join(exc.messages), "last_sync_at": timezone.now()}
        # Сохраняем читаемые строки даже при неизвестном offerId/нехватке остатка;
        # транзакция складского документа при этом полностью отменена.
        if not order.sale_id:
            values.update(status=payload.get("status", ""), substatus=payload.get("substatus", ""),
                          items=[{key: item[key] for key in ("id", "offerId", "offerName", "count", "prices") if key in item} for item in payload.get("items", [])])
        OrderMetadata.objects.filter(pk=order.pk).update(**values)
        raise


@transaction.atomic
def _apply_order(pk, payload):
    # Первая запись сериализует импорты одного документа также на SQLite.
    OrderMetadata.objects.filter(pk=pk).update(last_sync_at=timezone.now())
    order = OrderMetadata.objects.select_for_update().select_related("integration", "sale").get(pk=pk)
    integration = order.integration
    remote_time = aware_date(payload.get("updateDate"))
    if remote_time and order.updated_remote_at and remote_time < order.updated_remote_at:
        return order
    order.status = payload["status"]
    order.substatus = payload.get("substatus", "")
    order.fake = bool(payload.get("fake", False))
    order.created_remote_at = aware_date(payload.get("creationDate"))
    order.updated_remote_at = remote_time
    order.payment = {key: payload.get(key) for key in ("paymentType", "paymentMethod")}
    order.prices = payload.get("prices", {})
    delivery = payload.get("delivery", {})
    order.delivery = {key: delivery[key] for key in ("type", "serviceName", "deliveryServiceId", "warehouseId", "deliveryPartnerType", "dates", "shipment") if key in delivery}
    if delivery.get("boxesLayout"):
        order.boxes = delivery["boxesLayout"]
    order.items = [{key: item[key] for key in ("id", "offerId", "offerName", "count", "prices", "requiredInstanceTypes", "itemStatuses") if key in item} for item in payload.get("items", [])]
    order.shipped_once = order.shipped_once or order.status in SHIPPED or (
        order.status == "CANCELLED" and order.substatus in AFTER_SHIPMENT_CANCELLATIONS
    ) or any(
        status.get("status") in {"SHIPPED", "DELIVERED_TO_BUYER", "RETURNED", "LOST", "REJECTED"}
        for item in order.items for status in (item.get("itemStatuses") or [])
    )
    order.last_error = ""
    order.save()
    if order.fake:
        return order
    if not order.sale_id:
        if order.status == "CANCELLED":
            return order
        if not order.created_remote_at:
            raise ValidationError("Не указана дата создания заказа; автоматическое списание остановлено.")
        if order.created_remote_at and order.created_remote_at < integration.import_orders_from:
            order.last_error = "Исторический заказ до начала импорта: складское списание не выполнялось."
            order.save(update_fields=["last_error"])
            return order
        if order.status not in {"PROCESSING", "DELIVERY", "PICKUP", "DELIVERED"}:
            return order
        connections = {c.remote_offer.offer_id: c for c in OfferConnection.objects.select_related("remote_offer", "cd", "tech").filter(integration=integration, active=True, remote_offer__offer_id__in=[i["offerId"] for i in order.items])}
        lines, prices, references = [], {}, []
        if not order.items:
            raise ValidationError("Маркет вернул заказ без товарных строк.")
        for item in order.items:
            connection = connections.get(item["offerId"])
            if connection is None:
                raise ValidationError(f"Товар заказа не связан с номенклатурой GameBAT: {item['offerId']}.")
            quantity = item["count"]
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
                raise ValidationError("Маркет передал некорректное количество.")
            key = (connection.product_kind, connection.product.pk)
            if key in prices:
                raise ValidationError("В заказе повторяется товар. Требуется проверка состава.")
            prices[key] = item_amount(item)
            lines.append({"product_type": key[0], "product_id": key[1], "quantity": quantity})
            references.append((item, connection, prices[key] / quantity))
        try:
            sale = create_sale(actor=integration.operator, warehouse_id=integration.fulfillment_warehouse_id,
                               price_type=Sale.PriceType.YANDEX_MARKET, sale_type=Sale.SaleType.YANDEX_MARKET,
                               payment_method=Sale.PaymentMethod.BANK_ACCOUNT, lines=lines, external_prices=prices,
                               note=f"Заказ Яндекс Маркета №{order.order_id}. Выплата подтверждается отдельно.")
        except ValidationError as exc:
            if any("недостаточно товара" in message for message in exc.messages):
                raise ValidationError("Требуется внутреннее перемещение товара на склад выполнения заказов. " + " ".join(exc.messages)) from exc
            raise
        order.sale = sale
        order.stock_deducted = True
        order.save(update_fields=["sale", "stock_deducted"])
        for item, connection, unit_price in references:
            OrderLine.objects.create(order=order, remote_item_id=item["id"], connection=connection,
                                     quantity=item["count"], unit_price=unit_price.quantize(Decimal("0.01")))
    else:
        known = {line.remote_item_id: line for line in order.lines.select_related("connection__remote_offer")}
        changed = len(known) != len(order.items) or any(
            item["id"] not in known or known[item["id"]].quantity != item["count"]
            or known[item["id"]].connection.remote_offer.offer_id != item["offerId"] for item in order.items
        )
        if changed:
            order.last_error = "Состав заказа изменён на Маркете. Требуется сверка; повторное списание не выполнено."
            order.save(update_fields=["last_error"])
    if order.status == "CANCELLED":
        if not order.sale.is_cancelled:
            cancel_sale(actor=integration.operator, sale_id=order.sale_id,
                        comment=f"Маркет отменил заказ: {order.substatus}", _market=True,
                        restore_stock=not order.shipped_once)
            if not order.shipped_once:
                order.stock_deducted = False
                order.save(update_fields=["stock_deducted"])
        return order
    target = STATUS_MAP.get((order.status, order.substatus), STATUS_MAP.get((order.status, "")))
    sequence = list(Sale.OrderStatus.values)
    sale = Sale.objects.get(pk=order.sale_id)
    if target and not sale.is_cancelled:
        while sequence.index(sale.order_status) < sequence.index(target):
            sale = advance_order_status(actor=integration.operator, sale_id=sale.pk,
                                        next_status=sequence[sequence.index(sale.order_status) + 1], _market=True)
    return order


@transaction.atomic
def save_return(order, payload):
    OrderMetadata.objects.filter(pk=order.pk).update(last_sync_at=F("last_sync_at"))
    if int(payload["orderId"]) != order.order_id:
        raise ValidationError("Возврат относится к другому заказу.")
    allowed = ("id", "orderId", "creationDate", "updateDate", "refundStatus", "shipmentStatus", "items", "returnType", "fastReturn", "amount")
    result, _ = ReturnMetadata.objects.update_or_create(order=order, return_id=int(payload["id"]), defaults={
        "status": payload.get("shipmentStatus", ""), "kind": payload.get("returnType", ""),
        "snapshot": {key: payload[key] for key in allowed if key in payload},
    })
    return result


@transaction.atomic
def accept_return(*, return_pk, warehouse_id, actor):
    changed = ReturnMetadata.objects.filter(pk=return_pk, accepted_at__isnull=True).update(accepted_at=timezone.now())
    if not changed:
        raise ValidationError("Возврат уже принят на склад.")
    record = ReturnMetadata.objects.select_related("order__sale", "order__integration").get(pk=return_pk)
    order = record.order
    if order.fake or not order.sale_id or not order.stock_deducted or not order.shipped_once:
        raise ValidationError("По этому заказу нет невозвращённого складского списания.")
    if record.snapshot.get("fastReturn") or record.status in {"CANCELLED", "LOST", "UTILIZED", "PREPARED_FOR_UTILIZATION", "EXPROPRIATED"}:
        raise ValidationError("Статус возврата не допускает приём товара на склад.")
    order_lines = list(order.lines.select_for_update().select_related("connection__remote_offer", "connection__cd", "connection__tech"))
    by_offer = {line.connection.remote_offer.offer_id: line for line in order_lines}
    quantities = defaultdict(int)
    for item in record.snapshot.get("items", []):
        count = item.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValidationError("Некорректное количество в возврате.")
        quantities[item["shopSku"]] += count
    if not quantities:
        raise ValidationError("В возврате отсутствуют товары.")
    lines = []
    for offer, count in quantities.items():
        line = by_offer.get(offer)
        if line is None or line.returned_quantity + count > line.quantity:
            raise ValidationError("Возврат превышает невозвращённое количество продажи.")
        line.returned_quantity += count
        line.save(update_fields=["returned_quantity"])
        lines.append({"product_type": line.connection.product_kind, "product_id": line.connection.product.pk, "quantity": count})
    receive_return(actor=actor, warehouse_id=warehouse_id, lines=lines,
                   label=f"Возврат Маркета №{record.return_id}", sale_id=order.sale_id)
    record.warehouse_id = warehouse_id
    record.accepted_by = actor
    record.save(update_fields=["warehouse", "accepted_by"])
    AuditEvent.objects.create(integration=order.integration, actor=actor, action="accept_return", entity_id=str(record.pk), details={"warehouse_id": warehouse_id})
    return record
