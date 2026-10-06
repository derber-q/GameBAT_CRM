import hashlib
import ipaddress
import json

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Integration, WebhookEvent
from .queue import enqueue

EVENTS = {"ORDER_CREATED", "ORDER_CANCELLED", "ORDER_STATUS_UPDATED", "ORDER_RETURN_CREATED", "ORDER_RETURN_STATUS_UPDATED", "ORDER_UPDATED", "ORDER_CANCELLATION_REQUEST"}


def allowed_source(request):
    try:
        address = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
        trusted = [ipaddress.ip_network(value.strip()) for value in settings.YANDEX_MARKET_TRUSTED_PROXIES]
        if any(address in network for network in trusted):
            chain = [ipaddress.ip_address(value.strip()) for value in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if value.strip()]
            for hop in reversed(chain):
                address = hop
                if not any(hop in network for network in trusted):
                    break
        return any(address in ipaddress.ip_network(network) for network in settings.YANDEX_MARKET_WEBHOOK_NETWORKS)
    except ValueError:
        return False


@csrf_exempt
@require_POST
def notification(request):
    if not allowed_source(request):
        return JsonResponse({"error": {"message": "Источник уведомления не разрешён."}}, status=403)
    if len(request.body) > 1024 * 1024:
        return JsonResponse({"error": {"message": "Уведомление слишком велико."}}, status=400)
    try:
        payload = json.loads(request.body)
        kind = payload["notificationType"]
        if kind != "PING":
            integration = Integration.objects.get(campaign_id=int(payload["campaignId"]))
            order_id = int(payload["orderId"]) if kind in EVENTS else None
            return_id = int(payload["returnId"]) if kind in {"ORDER_RETURN_CREATED", "ORDER_RETURN_STATUS_UPDATED"} else None
            if (order_id is not None and order_id <= 0) or (return_id is not None and return_id <= 0):
                raise ValueError
            key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            with transaction.atomic():
                Integration.objects.filter(pk=integration.pk).update(last_sync_at=F("last_sync_at"))
                event, created = WebhookEvent.objects.get_or_create(integration=integration, key=key, defaults={
                    "event_type": kind, "order_id": order_id, "return_id": return_id,
                    "state": "pending" if kind in EVENTS else "ignored",
                })
                if created and kind in EVENTS:
                    transaction.on_commit(lambda: enqueue(integration, "event", event.pk, {"event_id": event.pk}))
    except (ValueError, TypeError, KeyError, Integration.DoesNotExist):
        return JsonResponse({"error": {"message": "Некорректное уведомление или неизвестный магазин."}}, status=400)
    return JsonResponse({"version": "1.0.0", "name": "ReSOURCE", "time": timezone.now().isoformat()})
