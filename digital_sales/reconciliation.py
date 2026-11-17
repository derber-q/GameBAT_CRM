"""Самостоятельное сообщение о балансе — основание сверки, но не автопополнения."""
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core.db_retry import retry_database_lock
from .models import (AuditEvent, BalanceObservation, DigitalOrder, Notification,
                     Supplier, SupplierMessage, SupplierPurchase)
from .parser import money
from .services import move_balance, record_id, require


def receipt_details(observation):
    """Ранее принятые квитанции читаются без переимпорта сообщений и изменения баланса."""
    message = observation.message
    if message.parsed.get('topup_receipt'):
        return message.parsed
    if message.kind != 'balance':
        return None
    from .crypto import decrypt
    from .parser import parse
    parsed = parse(decrypt(message.encrypted_payload).get('text', ''))
    if parsed and parsed.get('topup_receipt') and parsed.get('balance') == str(observation.balance):
        return parsed
    return None


def standalone(observation):
    """Ответ на заказ также относится к заказу, даже если в тексте только баланс."""
    message = observation.message
    if message.kind != 'balance' or message.order_id or message.parsed.get('numbers'):
        return False
    if SupplierMessage.objects.filter(supplier_id=message.supplier_id, chat_id=message.chat_id,
                                     message_id=message.message_id, order__isnull=False).exists():
        return False
    reply = message.parsed.get('reply_to_message_id')
    return not (reply and SupplierMessage.objects.filter(supplier_id=message.supplier_id,
        chat_id=message.chat_id, message_id=reply).filter(
            Q(order__isnull=False) | ~Q(kind='balance')).exists())


def credit_total(supplier, **filters):
    return supplier.movements.exclude(kind__in=['sale', 'reversal']).filter(**filters).aggregate(
        value=Sum('delta'))['value'] or Decimal(0)


def _unaccounted_topup(observation, *, ignore_later_receipts=False):
    """Закупки после снимка не уменьшают прежнее пополнение; новые внесения уменьшают.

    Для старых снимков исходные суммы выводятся из неизменяемых движений и
    сохранённого expected. Исторические записи при этом не переписываются.
    """
    if not standalone(observation):
        raise ValidationError('Баланс относится к заказу: отдельное поступление не требуется.')
    if observation.uncertain or observation.expected is None or observation.difference is None:
        raise ValidationError('Порядок событий не подтверждён. Нужна ручная сверка в CRM.')
    if observation.difference <= 0:
        raise ValidationError('В сообщении нет положительного расхождения. Требуется сверка, а не поступление.')
    credits = observation.credits_snapshot
    purchases = observation.purchases_snapshot
    if credits is None or purchases is None:
        credits = credit_total(observation.supplier, created_at__lte=observation.message.received_at)
        purchases = credits - observation.expected
    accounted = SupplierPurchase.objects.filter(order__supplier=observation.supplier,
        superseded_by__isnull=True, occurred_at__lte=observation.message.occurred_at).aggregate(
            value=Sum('amount'))['value'] or Decimal(0)
    incomplete = DigitalOrder.objects.filter(supplier=observation.supplier,
        ignored_at__isnull=True,
        messages__kind='checklist', messages__occurred_at__lte=observation.message.occurred_at).filter(
            Q(purchase__isnull=True) | Q(purchase__superseded_by__isnull=False)).exclude(state=DigitalOrder.State.CANCELLED).exists()
    if incomplete or accounted != purchases:
        raise ValidationError('Не все предшествующие закупки сверены или их состав изменён. Сначала проверьте заказы в CRM.')
    credited_since = credit_total(observation.supplier) - credits
    if ignore_later_receipts:
        # Подтверждение более поздней квитанции не погашает более раннюю.
        # Ручные внесения и общая сверка, напротив, должны уменьшать её остаток.
        later_receipts = observation.supplier.observations.filter(topup_movement__isnull=False,
            topup_movement__created_at__gt=observation.message.received_at).filter(
                Q(message__occurred_at__gt=observation.message.occurred_at) |
                Q(message__occurred_at=observation.message.occurred_at, pk__gt=observation.pk))
        seen = set()
        for later in later_receipts.select_related('message', 'topup_movement'):
            if later.topup_movement_id not in seen and receipt_details(later):
                credited_since -= later.topup_movement.delta
                seen.add(later.topup_movement_id)
    if credited_since < 0:
        raise ValidationError('После сообщения внесена уменьшающая корректировка. Проверьте баланс вручную в CRM.')
    amount = money(observation.difference - credited_since)
    if amount <= 0:
        raise ValidationError('Положительной неучтённой суммы нет. Пополнение не требуется.')
    return amount


def remaining_topup(observation):
    if observation.resolved_at:
        raise ValidationError('Это расхождение уже обработано.')
    receipt = receipt_details(observation)
    later = observation.supplier.observations.filter(message__kind='balance').filter(
        Q(message__occurred_at__gt=observation.message.occurred_at)
        | Q(message__occurred_at=observation.message.occurred_at, pk__gt=observation.pk))
    newer = [row for row in later.select_related('message', 'supplier').order_by('-message__occurred_at', '-pk') if standalone(row)]
    if not receipt:
        if newer:
            raise ValidationError('Есть более новое сообщение о балансе. Используйте его карточку.')
        return _unaccounted_topup(observation)
    if receipt.get('topup_issues') or not receipt.get('topup_amount'):
        raise ValidationError('; '.join(receipt.get('topup_issues') or ['Сумма пополнения требует проверки.']))
    if not standalone(observation) or observation.uncertain:
        raise ValidationError('Источник или порядок сообщения не подтверждён. Нужна ручная сверка.')
    latest_version = SupplierMessage.objects.filter(supplier_id=observation.supplier_id,
        chat_id=observation.message.chat_id, message_id=observation.message.message_id).order_by('-edit_version','-pk').first()
    if latest_version.pk != observation.message_id:
        raise ValidationError('Сообщение отредактировано. Используйте последнюю карточку пополнения.')
    amount = money(receipt['topup_amount'], positive=True)
    # Две квитанции можно подтвердить в любом порядке, но общая сумма не должна
    # превысить подтверждённый остаток по последнему самостоятельному снимку.
    available = min(_unaccounted_topup(newer[0] if newer else observation),
                    _unaccounted_topup(observation, ignore_later_receipts=True))
    if amount > available:
        raise ValidationError('Сумма пополнения уже учтена полностью или частично. Проверьте ручные внесения и баланс в CRM.')
    return amount


@retry_database_lock
@transaction.atomic
def apply_topup(*, actor, observation_id, displayed_amount):
    actor = require(actor, 'digital_sales.telegram_digital_sales',
                    'digital_sales.view_digital_reconciliation', 'digital_sales.topup_digital_balances')
    # Единый порядок блокировок с другими операциями поставщика; повторные
    # callback и разные сотрудники не должны создавать дубли движения.
    supplier_id = BalanceObservation.objects.values_list('supplier_id', flat=True).get(pk=observation_id)
    Supplier.objects.select_for_update().get(pk=supplier_id)
    observation = BalanceObservation.objects.select_for_update().select_related('message', 'supplier').get(pk=observation_id)
    if observation.topup_movement_id:
        return observation.topup_movement
    receipt = receipt_details(observation)
    if receipt:
        previous = BalanceObservation.objects.filter(supplier_id=supplier_id,
            message__chat_id=observation.message.chat_id, message__message_id=observation.message.message_id,
            topup_movement__isnull=False).select_related('topup_movement').first()
        if previous:
            raise ValidationError('Пополнение по этому сообщению уже проведено. Изменение квитанции требует ручной сверки.')
    amount = remaining_topup(observation)
    if amount != money(displayed_amount):
        raise ValidationError('Сумма расхождения изменилась. Проверьте обновлённую карточку и нажмите кнопку ещё раз.')
    movement = move_balance(actor=actor, supplier_id=supplier_id, amount=amount, kind='topup',
        reason=(f'Подтверждённое пополнение по сообщению №{observation.message_id}' if receipt else
                f'Поступление по самостоятельному сообщению о балансе №{observation.pk}'),
        operation_key=uuid.uuid5(uuid.NAMESPACE_URL,
            f'resource:digital:receipt:{supplier_id}:{observation.message.chat_id}:{observation.message.message_id}' if receipt else
            f'resource:digital:supplier-topup:{observation.pk}'))
    observation.topup_movement = movement
    observation.resolved_at = timezone.now()
    observation.resolution = f'Поступление {amount:.2f} ₽, движение №{movement.pk}'
    observation.save(update_fields=['topup_movement', 'resolved_at', 'resolution'])
    AuditEvent.objects.create(actor=actor, message=observation.message, kind='supplier_topup_reconciled',
                              detail=f'observation={observation.pk}; movement={movement.pk}')
    enqueue_observation(observation, event=f'applied:{movement.pk}')
    return movement


def card(observation):
    receipt = receipt_details(observation)
    text = ((f'💳 Пополнение баланса поставщика: {observation.supplier.name}\n' if receipt else
             f'Сверка баланса поставщика: {observation.supplier.name}\n') +
            f'Сообщено: {observation.balance:.2f} ₽\n')
    if receipt and receipt.get('topup_amount'):
        text += f'Сумма пополнения: +{money(receipt["topup_amount"]):.2f} ₽\n'
    if observation.expected is not None and observation.difference is not None:
        text += f'По учёту на момент сообщения: {observation.expected:.2f} ₽\nРазница: {observation.difference:+.2f} ₽\n'
    if observation.topup_movement_id:
        return {'text': text + f'✅ Поступление выполнено: +{observation.topup_movement.delta:.2f} ₽.'}
    try:
        amount = remaining_topup(observation)
    except ValidationError as exc:
        return {'text': text + '\n' + '; '.join(exc.messages)}
    return {'text': text + f'Неучтённое поступление: +{amount:.2f} ₽\nУчитывается наш баланс у поставщика.',
            'reply_markup': {'inline_keyboard': [[{
                'text': f'Подтвердить пополнение +{amount:.2f} ₽' if receipt else f'Выполнить поступление +{amount:.2f} ₽',
                'callback_data': f'dbal:{observation.pk}:{int(amount * 100)}'}]]}}


def enqueue_observation(observation, *, event='received'):
    from telegram_bots.models import StaffBotAccess
    from .notifications import eligible
    for access in StaffBotAccess.objects.select_related('user').filter(
            allowed=True, revoked_at__isnull=True, telegram_user_id__isnull=False):
        if eligible(access) and access.user.has_perm('digital_sales.view_digital_reconciliation'):
            Notification.objects.get_or_create(access=access, event_key=f'balance:{observation.pk}:{event}',
                defaults={'observation': observation, 'text': 'Сверка баланса поставщика'})


@retry_database_lock
@transaction.atomic
def remind_pending_topups(*, bot_id, chat_id, update_id):
    """Новая карточка в личном CRM-боте после ответа; деньги здесь не проводятся."""
    from telegram_bots.models import StaffBotAccess
    from .notifications import eligible
    access = StaffBotAccess.objects.select_for_update().select_related('user', 'bot').filter(
        bot_id=bot_id, telegram_user_id=chat_id, allowed=True, revoked_at__isnull=True).first()
    if not access or not eligible(access) or not access.user.has_perms([
        'digital_sales.view_digital_reconciliation', 'digital_sales.topup_digital_balances',
    ]):
        return 0
    count = 0
    observations = BalanceObservation.objects.filter(resolved_at__isnull=True, topup_movement__isnull=True,
        message__kind='balance').select_related('message', 'supplier').order_by('message__occurred_at', 'pk')
    for observation in observations:
        receipt = receipt_details(observation)
        if not receipt or not receipt.get('topup_amount') or not standalone(observation):
            continue
        # Старые версии квитанции и уже учтённые суммы не возвращают кнопку.
        if not card(observation).get('reply_markup'):
            continue
        key = f'balance:{observation.pk}:reminder:{update_id}'
        for older in Notification.objects.filter(access=access, observation=observation, state='queued',
                event_key__startswith=f'balance:{observation.pk}:reminder:').exclude(event_key=key):
            older.state = 'revoked'
            older.save(update_fields=['state'])
        _, created = Notification.objects.get_or_create(access=access, event_key=key,
            defaults={'observation':observation, 'text':'Напоминание о неподтверждённом пополнении'})
        count += int(created)
    return count


def handle(access, user, callback):
    data = callback.get('data') if callback else None
    if not isinstance(data, str) or not data.startswith('dbal:'):
        return None
    observation = None
    try:
        require(user, 'digital_sales.telegram_digital_sales', 'digital_sales.view_digital_reconciliation')
        parts = data.split(':')
        if len(parts) != 3:
            raise ValidationError('Откройте актуальное уведомление о балансе.')
        observation = BalanceObservation.objects.select_related('message', 'supplier').get(pk=record_id(parts[1]))
        cents = parts[2]
        if not cents.isascii() or not cents.isdecimal() or len(cents) > 20:
            raise ValidationError('Некорректная сумма поступления.')
        apply_topup(actor=user, observation_id=observation.pk, displayed_amount=Decimal(cents) / 100)
        observation.refresh_from_db()
        return card(observation)
    except ValidationError as exc:
        reply = card(observation) if observation else {'text': ''}
        reply['text'] = '; '.join(exc.messages) + '\n\n' + reply['text']
        return reply
    except PermissionDenied:
        return {'text': 'Нет прав на сверку или пополнение цифрового баланса. Обратитесь к администратору CRM.'}
    except BalanceObservation.DoesNotExist:
        return {'text': 'Уведомление не найдено. Откройте актуальную сверку в CRM.'}
