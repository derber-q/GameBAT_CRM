"""Данные для управления связанным заказом Маркета из карточки и списка продаж."""
from django.db.models import Prefetch, Exists, OuterRef
from .models import MarketPrintJob

from yandex_market.models import LabelDocument, SyncJob
from yandex_market.orders import available_actions


def with_market_controls(queryset):
    return queryset.annotate(has_market_label_printed=Exists(MarketPrintJob.objects.filter(
        order_id=OuterRef('yandex_order__pk'), printed_at__isnull=False,
    ))).select_related('yandex_order__integration').prefetch_related(Prefetch(
        'yandex_order__labels', to_attr='sale_labels',
        queryset=LabelDocument.objects.filter(box_id__isnull=True, shipment_id__isnull=True).order_by('-pk'),
    ), Prefetch('yandex_order__integration__jobs', to_attr='sale_order_jobs',
        queryset=SyncJob.objects.filter(kind__in=['order', 'order_action', 'boxes']).order_by('-updated_at'),
    ))


def market_context(sale, user, *, editable=True):
    order = getattr(sale, 'yandex_order', None)
    if not order:
        return None
    labels = {
        'PROCESSING': 'В обработке', 'DELIVERY': 'Передан в доставку', 'PICKUP': 'В пункте выдачи',
        'DELIVERED': 'Доставлен покупателю', 'CANCELLED': 'Отменён', 'UNPAID': 'Ожидает оплаты на Маркете',
        'PENDING': 'Ожидает обработки', 'RETURNED': 'Возвращён', 'PARTIALLY_RETURNED': 'Частично возвращён',
    }
    status_label = labels.get(order.status, order.status or 'Статус не получен')
    if order.status == 'PROCESSING' and order.substatus == 'READY_TO_SHIP':
        status_label = 'Готов к отгрузке'
    actions = available_actions(order).copy()
    needs_boxes = 'ready' in actions and not order.boxes
    if needs_boxes:
        actions.pop('ready')
    can_manage = (editable and not sale.is_cancelled and not sale.is_completed and not order.fake
                  and order.integration.enabled and user.has_perm('yandex_market.manage_orders'))
    documents = order.sale_labels
    latest_request = next((job for job in order.integration.sale_order_jobs
                           if job.payload.get('order_id') == order.order_id), None)
    return {'order': order, 'status_label': status_label, 'actions': actions if can_manage else {},
            'can_manage': can_manage, 'needs_boxes': needs_boxes,
            'can_print': user.has_perm('yandex_market.print_labels'),
            'can_view_order': user.has_perm('yandex_market.view_integration'),
            'label_printed': sale.has_market_label_printed,
            'label': documents[0] if documents else None, 'latest_request': latest_request}
