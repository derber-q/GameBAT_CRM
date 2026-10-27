"""Внутреннее подтверждение внимания сотрудника без изменения статусов заказа."""
import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from yandex_market.services import audit
from .models import MarketOrderAttention

logger = logging.getLogger('gamebat.business')
REPEAT_SECONDS = 600


def can_acknowledge(user):
    return user.is_active and user.has_perm('sales.view_sales') and user.has_perm('yandex_market.manage_orders')


def pending_attention():
    return MarketOrderAttention.objects.filter(acknowledged_at__isnull=True).select_related(
        'order__sale', 'order__integration').order_by('notification_started_at', 'pk')


def require_staff_acknowledgement(order):
    if not order.sale_id or order.fake:
        raise ValidationError('Подтверждение создаётся только для новой действительной продажи Маркета.')
    record, created = MarketOrderAttention.objects.get_or_create(order=order)
    if created:
        audit(order.integration, None, 'staff_acknowledgement_required', order.order_id, sale_id=order.sale_id)
        logger.info('Новый заказ ожидает сотрудника: order_id=%s sale_id=%s', order.order_id, order.sale_id)
    return record


def attention_snapshot(user):
    if not user.is_active or not user.has_perm('sales.view_sales'):
        raise PermissionDenied
    allowed = can_acknowledge(user)
    orders = [{'id': row.pk, 'order_id': str(row.order.order_id), 'sale_id': row.order.sale_id,
               'started_at': row.notification_started_at.isoformat(),
               'detail_url': reverse('sales:detail', args=[row.order.sale_id])
                   if user.has_perm('sales.view_sale_detail') else '',
               'ack_url': reverse('sales:market_acknowledge', args=[row.pk]) if allowed else ''}
              for row in pending_attention()]
    return {'server_now': timezone.now().isoformat(), 'repeat_seconds': REPEAT_SECONDS,
            'count': len(orders), 'orders': orders, 'can_acknowledge': allowed}


@transaction.atomic
def acknowledge_order(*, actor, attention_id):
    if not can_acknowledge(actor):
        raise PermissionDenied
    # Первая запись сериализует конкурирующие подтверждения также на SQLite.
    changed = MarketOrderAttention.objects.filter(pk=attention_id, acknowledged_at__isnull=True).update(
        acknowledged_at=timezone.now(), acknowledged_by=actor)
    record = MarketOrderAttention.objects.select_related('order__integration', 'acknowledged_by').get(pk=attention_id)
    if changed:
        audit(record.order.integration, actor, 'staff_order_acknowledged', record.order.order_id,
              sale_id=record.order.sale_id, acknowledged_at=record.acknowledged_at.isoformat())
        logger.info('Заказ принят сотрудником: order_id=%s sale_id=%s user_id=%s',
                    record.order.order_id, record.order.sale_id, actor.pk)
    return record
