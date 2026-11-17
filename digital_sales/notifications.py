"""Outbox хранит только публичную часть заказа, без оригиналов и секретов товара."""
from django.conf import settings
from django.contrib.auth import get_user_model
from telegram_bots.models import StaffBotAccess
from telegram_bots.access import check_access, BotDenied
from .models import DigitalOrder, Notification
from .parser import money


def enqueue_alert(event, text):
    url = str(getattr(settings, 'DIGITAL_SALES_CRM_URL', 'http://127.0.0.1:8000')).rstrip('/') + '/crm/digital/'
    for access in StaffBotAccess.objects.filter(allowed=True, revoked_at__isnull=True, telegram_user_id__isnull=False):
        if eligible(access) and (not event.startswith(('balance:', 'cancel_balance:', 'supplier_topup:')) or access.user.has_perm('digital_sales.view_digital_reconciliation')):
            Notification.objects.get_or_create(access=access, event_key=event[:100],
                                              defaults={'text': (text + '\n' + url)[:3900]})


def eligible(access):
    try:
        user = check_access(access)
        return user.has_perms(['sales.create_sale', 'digital_sales.create_digital_sales', 'digital_sales.telegram_digital_sales'])
    except BotDenied:
        return False


def notification_allowed(row):
    if row.event_key.startswith('price_dispatch:'):
        from digital_prices.dispatch import alert_allowed
        return alert_allowed(row.access)
    if not eligible(row.access):
        return False
    if row.order_id:
        current_order = DigitalOrder.objects.only('state', 'ignored_at').get(pk=row.order_id)
        if current_order.processing_stopped and not row.event_key.startswith(
                (f'order:{row.order_id}:ignored:', f'order:{row.order_id}:cancelled:')):
            return False
    if row.event_key.startswith(('balance:', 'cancel_balance:', 'supplier_topup:')):
        current = get_user_model().objects.filter(pk=row.access.user_id, is_active=True).first()
        if not current or not current.has_perm('digital_sales.view_digital_reconciliation'):
            return False
        if row.observation_id:
            from .reconciliation import standalone
            if ':reminder:' in row.event_key:
                from .models import BalanceObservation
                from .reconciliation import card
                current = BalanceObservation.objects.select_related('message', 'supplier', 'topup_movement').get(pk=row.observation_id)
                if current.resolved_at or current.topup_movement_id or not card(current).get('reply_markup'):
                    return False
            return standalone(row.observation)
        if row.event_key.startswith('balance:'):
            # Старый outbox мог содержать ещё не отправленные предупреждения из
            # чек-листов. Не доставляем их после обновления и не меняем историю.
            from .models import BalanceObservation
            from .reconciliation import standalone
            fingerprint = row.event_key.rsplit(':', 1)[-1]
            observation = BalanceObservation.objects.filter(message__fingerprint=fingerprint).select_related('message').first()
            return bool(observation and standalone(observation))
        return True
    return True


def order_url(order):
    return str(getattr(settings, 'DIGITAL_SALES_CRM_URL', 'http://127.0.0.1:8000')).rstrip('/') + f'/crm/digital/orders/{order.pk}/'


def enqueue_order(order, *, event='ready', extra=''):
    if order.processing_stopped and not event.startswith(('ignored:', 'cancelled:')):
        return
    numbers = ', '.join('#' + value for value in order.references.values_list('number', flat=True)) or 'без номера'
    lines = '\n'.join(f"• {row['name'][:120]} — {row['cost']} ₽" for row in order.items[:20])
    text = (f'Цифровой заказ №{order.pk}: {order.get_state_display()}\nПоставщик: {numbers}\n{lines}\n'
            f'Себестоимость: {money(order.cost):.2f} ₽\n{extra}\n{order_url(order)}')[:3900]
    for access in StaffBotAccess.objects.select_related('user', 'bot').filter(allowed=True, revoked_at__isnull=True, telegram_user_id__isnull=False):
        if eligible(access):
            Notification.objects.get_or_create(access=access, event_key=f'order:{order.pk}:{event}',
                                              defaults={'order': order, 'text': text})
