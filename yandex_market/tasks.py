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
from .services import refresh_catalog, refresh_trade_snapshots, sync_product, sync_price_stock_batch, connections_with_stock

RETRY_DELAYS = (60, 180, 300, 900, 1800)


def reconcile_orders(integration, client):
    # Контрольный опрос не заменяет webhook. Повторная обработка идемпотентна.
    for payload in client.pages("getBusinessOrders", body={"campaignIds": [integration.campaign_id], "programTypes": ["FBS"]}, key="orders", limit=50):
        try:
            import_order(integration, payload)
        except ValidationError:
            continue
    # Открытые старые заказы могут выйти за стандартное окно API в 30 дней.
    for order in integration.orders.exclude(status__in=["CANCELLED", "DELIVERED", "RETURNED", "PARTIALLY_RETURNED"]).exclude(
        status="", sale__isnull=True,
    ).iterator():
        try:
            import_order(integration, client.order(order.order_id))
        except ValidationError:
            continue
        except MarketError as exc:
            if exc.code != "ORDER_NOT_FOUND":
                raise
            # Отсутствие одного заказа не останавливает остатки и другие заказы.
            order.last_error = str(exc)
            order.last_sync_at = timezone.now()
            order.save(update_fields=["last_error", "last_sync_at"])


def reconcile_returns(integration, client):
    for payload in client.pages("getReturns", key="returns", limit=50):
        order, _ = OrderMetadata.objects.get_or_create(integration=integration, order_id=payload["orderId"])
        save_return(order, payload)


def reconcile(integration, client):
    started = timezone.now()
    errors = []
    stages = (
        ("Заказы", lambda: reconcile_orders(integration, client)),
        ("Возвраты", lambda: reconcile_returns(integration, client)),
        ("Каталог", lambda: refresh_catalog(integration, client=client, include_trade=False)),
        ("Цены и остатки", lambda: refresh_trade_snapshots(integration, client=client)),
    )
    for label, stage in stages:
        try:
            stage()
        except (MarketError, ValidationError) as exc:
            errors.append((label, exc))
    mismatches = {}
    unread = []
    for connection in connections_with_stock(OfferConnection.objects.filter(integration=integration, active=True, managed=True).select_related("remote_offer", "cd", "tech")):
        desired = connection.physical_stock if connection.sell_on_yandex and not connection.product.is_archived else 0
        remote = connection.remote_offer
        prices_checked = bool(remote.price_checked_at and remote.price_checked_at >= started)
        stocks_checked = bool(remote.stock_checked_at and remote.stock_checked_at >= started)
        if not stocks_checked or (connection.sell_on_yandex and not prices_checked):
            unread.append(remote.offer_id)
        needs_display = connection.resume_display_pending and connection.sell_on_yandex and not connection.product.is_archived
        if ((needs_display and prices_checked and stocks_checked)
                or (stocks_checked and remote.remote_stock != desired)
                or (prices_checked and connection.sell_on_yandex and remote.remote_price != connection.product.yandex_market_price)):
            mismatches.setdefault((prices_checked, stocks_checked), []).append(connection.pk)
    for (prices_checked, stocks_checked), ids in mismatches.items():
        scope = "reconciliation" if prices_checked and stocks_checked else ("reconciliation-prices" if prices_checked else "reconciliation-stocks")
        enqueue(integration, "products", scope, {"connection_ids": ids,
            "sync_prices": prices_checked, "sync_stocks": stocks_checked}, delay=3)
    if unread and not errors:
        errors.append(("Цены и остатки", MarketError(
            f"API не вернул свежие цену или остаток для {len(unread)} связанных товаров.",
            "INCOMPLETE_TRADE_SNAPSHOT", retryable=True)))
    if errors:
        message = "; ".join(f"{label}: {exc}" for label, exc in errors)
        retryable = any(isinstance(exc, MarketError) and exc.retryable for _, exc in errors)
        delay = max((exc.retry_after for _, exc in errors if isinstance(exc, MarketError)), default=0)
        raise MarketError(message, "RECONCILIATION_INCOMPLETE", retryable=retryable, retry_after=delay)
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
        sync_price_stock_batch(integration, payload["connection_ids"], client=client,
            sync_prices=payload.get("sync_prices", True), sync_stocks=payload.get("sync_stocks", True))
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
        # Восстановление периодической задачи, остановленной предыдущей версией worker.
        SyncJob.objects.filter(key=f"ym:{integration.pk}:periodic", state="error", run_after__lte=now).update(
            state="pending", lease=None, updated_at=now,
        )
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
    elif retry or periodic:
        if periodic and error and not retry:
            delay = 900
        selector.update(state="pending", lease=None, attempts=F("attempts") + 1 if error else 0, last_error=error,
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
