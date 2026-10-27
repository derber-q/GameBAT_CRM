"""Закрытые endpoints внутреннего подтверждения; API Маркета не вызывается."""
import logging

from django.db import OperationalError
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_all, permission_required_any
from .models import MarketOrderAttention
from .notifications import acknowledge_order, attention_snapshot, can_acknowledge, pending_attention

logger = logging.getLogger('gamebat.business')


@require_GET
@never_cache
@permission_required_any('sales.view_sales')
def pending_orders(request):
    return render(request, 'sales/market_pending.html', {
        'attention_rows': pending_attention(), 'can_acknowledge': can_acknowledge(request.user),
    })


@require_GET
@never_cache
@permission_required_any('sales.view_sales')
def notification_status(request):
    try:
        return JsonResponse(attention_snapshot(request.user))
    except OperationalError:
        logger.exception('Ошибка чтения уведомлений заказов Маркета')
        return JsonResponse({'error': 'Не удалось обновить уведомления. Повторяем соединение.'}, status=503)


@require_POST
@never_cache
@permission_required_all('sales.view_sales', 'yandex_market.manage_orders')
def acknowledge(request, attention_id):
    try:
        record = acknowledge_order(actor=request.user, attention_id=attention_id)
        snapshot = attention_snapshot(request.user)
    except MarketOrderAttention.DoesNotExist:
        raise Http404('У заказа нет внутреннего требования подтверждения.') from None
    except OperationalError:
        logger.exception('Ошибка подтверждения внимания сотрудника: attention_id=%s', attention_id)
        return JsonResponse({'error': 'База занята. Повторите подтверждение через несколько секунд.'}, status=503)
    return JsonResponse({**snapshot, 'acknowledged_id': record.pk,
        'acknowledged_at': record.acknowledged_at.isoformat(), 'acknowledged_by': record.acknowledged_by_id})
