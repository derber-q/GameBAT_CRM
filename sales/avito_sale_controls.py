"""Статусы связанной продажи CRM; сами заказы на Avito эти действия не меняют."""
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse

from .avito_orders import order_id
from .models import AvitoBrowserOrder, Sale
from .services import next_order_status, can_mark_paid, advance_order_status, mark_sale_paid, cancel_sale


@lru_cache(maxsize=1)
def status_styles():
    """Те же классы и цвета, что в CRM; отдельной копии палитры в расширении нет."""
    return (Path(settings.BASE_DIR) / 'static/css/sales-list.css').read_text(encoding='utf-8')


def can_view(sale, actor):
    return actor.has_perm('sales.view_completed_sales' if sale.is_completed else 'sales.view_sales')


def summary(order, actor):
    sale = order.sale
    state = None
    if sale and can_view(sale, actor):
        editable = not sale.is_cancelled and not sale.is_completed and sale.sale_type == Sale.SaleType.AVITO
        next_status = next_order_status(sale) if editable and actor.has_perm('sales.advance_order_status') else None
        state = dict(version=sale.updated_at.isoformat(), order_status=sale.order_status,
            order_label=sale.get_order_status_display(), payment_status=sale.payment_status,
            payment_label=sale.get_payment_status_display(), next_order=next_status,
            next_order_label=Sale.OrderStatus(next_status).label if next_status else '',
            can_mark_paid=bool(editable and can_mark_paid(sale) and actor.has_perm('sales.mark_sale_paid')),
            can_cancel=bool(not sale.is_cancelled and sale.sale_type == Sale.SaleType.AVITO and actor.has_perm('sales.cancel_sale')),
            total=str(sale.total_amount), payment_method_label=sale.get_payment_method_display(),
            cancelled=sale.is_cancelled, completed=sale.is_completed)
    return dict(id=str(order.pk), sale_number=sale.visible_id if sale else None,
        sale_url=reverse('sales:detail', args=[sale.pk]) if sale else None,
        cancelled=bool(sale and sale.is_cancelled), sale=state)


@transaction.atomic
def change_status(data, actor):
    """Права, текущая версия и штатные сервисы проверяются до проведения операции."""
    order = AvitoBrowserOrder.objects.select_related('sale').get(external_id=order_id(data.get('order_id')))
    if not order.sale_id:
        raise ValidationError('Сначала создайте продажу CRM.')
    sale = Sale.objects.select_for_update().get(pk=order.sale_id)
    field = data.get('field')
    permission = {'order':'sales.advance_order_status', 'payment':'sales.mark_sale_paid'}.get(field)
    if not permission:
        raise ValidationError('Неизвестный статус.')
    if not can_view(sale, actor) or not actor.has_perm(permission):
        raise PermissionDenied('Недостаточно прав для изменения статуса продажи.')
    if data.get('confirmed') is not True:
        raise ValidationError('Подтвердите изменение статуса.')
    if sale.sale_type != Sale.SaleType.AVITO:
        raise ValidationError('Эта продажа не относится к Avito.')
    if data.get('version') != sale.updated_at.isoformat() or sale.is_cancelled or sale.is_completed:
        raise ValidationError('Продажа уже изменена. Обновите данные и повторите действие.', code='stale_sale')
    if field == 'order':
        sale = advance_order_status(actor=actor, sale_id=sale.pk, next_status=data.get('value'))
    else:
        if data.get('value') != Sale.PaymentStatus.PAID:
            raise ValidationError('Этот переход статуса оплаты недопустим.')
        # В расширении подтверждается полная сумма. Частичные расчёты доступны в CRM.
        sale = mark_sale_paid(actor=actor, sale_id=sale.pk)
    order.sale = sale
    return summary(order, actor)


@transaction.atomic
def cancel(data, actor):
    """«Удалить» в расширении означает штатную отмену с сохранением истории и связи."""
    order = AvitoBrowserOrder.objects.select_related('sale').get(external_id=order_id(data.get('order_id')))
    if not order.sale_id:
        raise ValidationError('У заказа нет продажи CRM.')
    sale = Sale.objects.select_for_update().get(pk=order.sale_id)
    if not can_view(sale, actor) or not actor.has_perm('sales.cancel_sale'):
        raise PermissionDenied('Недостаточно прав для отмены продажи.')
    if data.get('confirmed') is not True:
        raise ValidationError('Подтвердите отмену продажи.')
    if sale.sale_type != Sale.SaleType.AVITO:
        raise ValidationError('Эта продажа не относится к Avito.')
    if sale.is_cancelled or data.get('version') != sale.updated_at.isoformat():
        raise ValidationError('Продажа уже изменена. Обновите данные и повторите действие.', code='stale_sale')
    comment = data.get('comment')
    if not isinstance(comment, str) or not comment.strip() or len(comment) > 2000:
        raise ValidationError('Укажите причину отмены (до 2000 символов).')
    order.sale = cancel_sale(actor=actor, sale_id=sale.pk, comment=comment).sale
    return summary(order, actor)
