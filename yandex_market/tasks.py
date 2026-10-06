"""Короткий захват задачи; HTTP всегда выполняется за пределами транзакции."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.db.models import F, Case, When, Value, IntegerField
from django.utils import timezone

from warehouse.inventory import global_stock
from .client import MarketError, YandexMarketClient
from .documents import process_label
from .models import Integration, LabelDocument, OfferConnection, OrderMetadata, RemoteOffer, ReturnMetadata, SyncJob, WebhookEvent
from .orders import action_payload, import_order, save_return
from .queue import enqueue
from .services import refresh_catalog, sync_product, sync_price_stock_batch, connections_with_stock

RETRY_DELAYS = (60, 180, 300, 900, 1800)


def reconcile(integration, client):
    # Контрольный опрос не заменяет webhook. Повторная обработка идемпотентна.
    for payload in client.pages("getBusinessOrders", body={"campaignIds": [integration.campaign_id], "programTypes": ["FBS"]}, key="orders", limit=50):
        try:
            import_order(integration, payload)
        except ValidationError:
            continue
    # Открытые старые заказы могут выйти за стандартное окно API в 30 дней.
    for order in integration.orders.exclude(status__in=["CANCELLED", "DELIVERED"]).iterator():
        try:
            import_order(integration, client.order(order.order_id))
        except ValidationError:
            continue
    for payload in client.pages("getReturns", key="returns", limit=50):
        order, _ = OrderMetadata.objects.get_or_create(integration=integration, order_id=payload["orderId"])
        save_return(order, payload)
    refresh_catalog(integration, client=client)
    mismatches = []
    for connection in connections_with_stock(OfferConnection.objects.filter(integration=integration, active=True, managed=True).select_related("remote_offer", "cd", "tech")):
        desired = connection.physical_stock if connection.sell_on_yandex and not connection.product.is_archived else 0
        remote = connection.remote_offer
        if remote.remote_stock != desired or (connection.sell_on_yandex and remote.remote_price != connection.product.yandex_market_price):
            mismatches.append(connection.pk)
    if mismatches:
        enqueue(integration, "products", "reconciliation", {"connection_ids": mismatches}, delay=3)
    integration.last_sync_at = timezone.now()
    integration.last_error = ""
    integration.save(update_fields=["last_sync_at", "last_error"])


def process(job):
    integration = job.integration
    client = YandexMarketClient(integration, job=job)
    payload = job.payload
    if job.kind == "catalog":
        refresh_catalog(integration, client=client)
    elif job.kind == "reconcile":
        reconcile(integration, client)
    elif job.kind == "product":
        sync_product(payload["connection_id"], client=client, force=payload.get("force", False))
    elif job.kind == "products":
        sync_price_stock_batch(integration, payload["connection_ids"], client=client)
    elif job.kind in {"order", "event", "order_action", "boxes"}:
        event = WebhookEvent.objects.get(pk=payload["event_id"]) if job.kind == "event" else None
        order_id = event.order_id if event else payload["order_id"]
        if event:
            WebhookEvent.objects.filter(pk=event.pk).update(attempts=F("attempts") + 1, state="processing")
        order = import_order(integration, client.order(order_id))
        if job.kind == "order_action":
            if not integration.enabled:
                raise ValidationError("Обмен с Маркетом выключен.")
            desired = payload["action"]
            already_done = (desired == "ready" and (order.substatus == "READY_TO_SHIP" or order.status in {"DELIVERY", "PICKUP", "DELIVERED"})) or (desired == "cancel" and order.status == "CANCELLED")
            if not already_done:
                client.call("updateOrderStatus", params={"orderId": order_id}, body=action_payload(order, desired), entity_id=order_id)
                import_order(integration, client.order(order_id))
        if job.kind == "boxes":
            if not integration.enabled or order.status != "PROCESSING" or order.substatus != "STARTED":
                raise ValidationError("Коробки можно изменять только до готовности к отгрузке.")
            from .packing import validate_boxes
            validate_boxes(order, payload["boxes"])
            response = client.call("setOrderBoxLayout", params={"orderId": order_id}, body={"boxes": payload["boxes"], "allowRemove": False}, entity_id=order_id)
            order.boxes = response.get("result", response).get("boxes", [])
            order.save(update_fields=["boxes"])
            labels = client.call("getOrderLabelsData", params={"orderId": order_id}, entity_id=order_id).get("result", {})
            order.delivery["labelBoxes"] = [{key: row[key] for key in ("boxId", "shipmentId", "place") if key in row} for row in labels.get("parcelBoxLabels", [])]
            order.save(update_fields=["delivery"])
        if event and event.return_id:
            remote_return = client.call("getReturn", params={"orderId": order_id, "returnId": event.return_id})["result"]
            save_return(order, remote_return)
        if event:
            event.processed_at = timezone.now()
            event.state = "done"
            event.last_error = ""
            event.save(update_fields=["processed_at", "state", "last_error"])
    elif job.kind == "label":
        process_label(payload["document_id"], client)
    else:
        raise ValidationError("Неизвестный тип задания Маркета.")


def ensure_periodic_jobs():
    now = timezone.now()
    SyncJob.objects.filter(state="running", updated_at__lt=now - timedelta(minutes=20)).update(state="pending", lease=None, run_after=now)
    for integration in Integration.objects.filter(enabled=True):
        SyncJob.objects.get_or_create(key=f"ym:{integration.pk}:periodic", defaults={"integration": integration, "kind": "reconcile"})
        # Восстановление inbox, если процесс завершился между commit и callback очереди.
        for event_id in WebhookEvent.objects.filter(integration=integration, state="pending").values_list("pk", flat=True)[:100]:
            if not SyncJob.objects.filter(key=f"ym:{integration.pk}:event:{event_id}").exists():
                enqueue(integration, "event", event_id, {"event_id": event_id})


def claim_job():
    candidates = SyncJob.objects.filter(state="pending", run_after__lte=timezone.now()).annotate(priority=Case(
        When(kind__in=["event", "order", "order_action"], then=Value(0)), When(kind="reconcile", then=Value(2)),
        default=Value(1), output_field=IntegerField())).order_by("priority", "run_after", "pk")
    candidate = candidates.first()
    if candidate is None:
        return None
    lease = uuid.uuid4()
    claimed = SyncJob.objects.filter(pk=candidate.pk, state="pending", generation=candidate.generation).update(
        state="running", lease=lease, claimed_generation=F("generation"), updated_at=timezone.now(),
    )
    return SyncJob.objects.select_related("integration", "actor").get(pk=candidate.pk) if claimed else None


def process_one_job():
    ensure_periodic_jobs()
    job = claim_job()
    if job is None:
        return False
    error, retry, delay = "", False, 0
    try:
        if not job.integration.enabled and job.kind not in {"catalog", "label"}:
            raise ValidationError("Фоновый обмен выключен. Включите его в настройках и повторите задачу.")
        process(job)
    except MarketError as exc:
        error, retry = str(exc), exc.retryable
        delay = exc.retry_after or RETRY_DELAYS[min(job.attempts, len(RETRY_DELAYS) - 1)]
    except ValidationError as exc:
        error = " ".join(exc.messages)
    except OperationalError:
        error, retry, delay = "База данных занята. Задание будет повторено.", True, 5
    except Exception as exc:
        # Не включать URL/тела ответа/реквизиты в неожиданные исключения.
        error = f"Внутренняя ошибка обработки ({type(exc).__name__}). Проверьте данные задания."
    selector = SyncJob.objects.filter(pk=job.pk, lease=job.lease, state="running")
    current = selector.first()
    if current is None:
        return True
    changed = current.generation != job.claimed_generation
    periodic = job.key.endswith(":periodic")
    if changed:
        selector.update(state="pending", lease=None, attempts=0, last_error="", updated_at=timezone.now())
    elif retry or (periodic and not error):
        selector.update(state="pending", lease=None, attempts=F("attempts") + (1 if error else 0), last_error=error,
                        run_after=timezone.now() + timedelta(seconds=delay if error else 900), updated_at=timezone.now())
    else:
        selector.update(state="error" if error else "done", lease=None, last_error=error, updated_at=timezone.now())
    if error:
        if job.kind == "product":
            OfferConnection.objects.filter(pk=job.payload.get("connection_id")).update(state="error", last_error=error)
        elif job.kind == "products":
            OfferConnection.objects.filter(pk__in=job.payload.get("connection_ids", []), integration=job.integration).update(state="error", last_error=error)
        elif job.kind == "event":
            WebhookEvent.objects.filter(pk=job.payload.get("event_id")).update(state="error", last_error=error)
        elif job.kind == "label":
            LabelDocument.objects.filter(pk=job.payload.get("document_id")).update(state="processing" if retry else "error", last_error=error)
        elif job.kind == "reconcile":
            Integration.objects.filter(pk=job.integration_id).update(last_error=error)
    return True
