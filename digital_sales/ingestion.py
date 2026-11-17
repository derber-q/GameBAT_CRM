"""Внешние события сохраняются атомарно; отправка сообщений здесь запрещена."""
import hashlib
import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from core.db_retry import retry_database_lock
from .crypto import encrypt
from .models import (DigitalBot, DigitalOrder, Supplier, SupplierMessage, SupplierPurchase,
                     OrderReference, BalanceObservation, BalanceMovement, AuditEvent)
from .parser import parse, money


def _issue(order, reason):
    if order.processing_stopped:
        return
    if not order.sale_id:
        order.state = DigitalOrder.State.REVIEW
    if reason not in order.review_reason:
        order.review_reason = '; '.join(filter(None, [order.review_reason, reason]))[:300]
    order.revision += 1
    order.save(update_fields=['state', 'review_reason', 'revision', 'updated_at'])
    AuditEvent.objects.create(order=order, kind='review_required', detail=reason[:300])
    from .notifications import enqueue_alert
    enqueue_alert(f'review:{order.pk}:{hashlib.sha256(reason.encode()).hexdigest()[:24]}',
                  f'Цифровой заказ №{order.pk} требует проверки: {reason[:300]}')


def _refresh(order, *, notify=True):
    if order.source == 'api_v2':
        return  # Выполнение и деньги принадлежат API-заказу, сообщение не создаёт вторую продажу.
    if order.sale_id or order.processing_stopped:
        return
    if not order.review_reason:
        order.state = (DigitalOrder.State.READY if order.goods_received and order.checklist_received else
                       DigitalOrder.State.GOODS if order.checklist_received else DigitalOrder.State.CHECKLIST)
        order.revision += 1
        order.save(update_fields=['state', 'revision', 'updated_at'])
    # Покупателя и цену можно подготовить до готовности. Подтверждение продажи
    # по-прежнему проверяет полный состав, готовность и отсутствие расхождений.
    if notify:
        from .notifications import enqueue_order
        enqueue_order(order, event=f'updated:{order.revision}')


def _clear_resolved_status_warnings(order, parsed):
    if parsed.get('kind') != 'checklist' or parsed.get('issues') or not order.checklist_received:
        return
    resolved = {'Нет выполненного статуса', 'Нет подтверждения оплаты поставщику'}
    remaining = '; '.join(part for part in order.review_reason.split('; ') if part and part not in resolved)
    if remaining != order.review_reason:
        order.review_reason = remaining
        order.save(update_fields=['review_reason'])
        AuditEvent.objects.create(order=order, kind='checklist_status_updated', detail='Прежние замечания о статусе устранены')


def _same_checklist_snapshot(before, after):
    """Изменение статуса не равно изменению закупки: сохраняем контроль состава/суммы/номеров."""
    def rows(parsed):
        return sorted((row['name'], money(row['cost']), str(row.get('number') or ''))
                      for row in parsed.get('items', []))
    return (before.get('kind') == after.get('kind') == 'checklist'
        and rows(before) == rows(after)
        and before.get('total') == after.get('total')
        and sorted(before.get('numbers', [])) == sorted(after.get('numbers', [])))


def expected_balance(supplier):
    credits = supplier.movements.exclude(kind__in=['sale', 'reversal']).aggregate(value=Sum('delta'))['value'] or Decimal(0)
    purchases = SupplierPurchase.objects.filter(order__supplier=supplier, superseded_by__isnull=True).aggregate(value=Sum('amount'))['value'] or Decimal(0)
    from digital_shop.models import ConfirmedRefund
    refunds = ConfirmedRefund.objects.filter(line__digital_order__supplier=supplier).aggregate(value=Sum('amount'))['value'] or Decimal(0)
    return credits - purchases + refunds


def _observation(message, parsed, *, late=False):
    if parsed.get('balance') is None:
        return
    supplier = message.supplier
    actual = money(parsed['balance'])
    # Первый достоверный остаток задаёт исходную точку только при отсутствии ручного учёта.
    previous = supplier.observations.filter(uncertain=False).select_related('message').order_by('-message__occurred_at', '-pk').first()
    uncertain = late or bool(message.forwarded and parsed.get('unverified_forward'))
    if not previous and not supplier.movements.exists() and not uncertain and not parsed.get('topup_receipt'):
        known_cost = SupplierPurchase.objects.filter(order__supplier=supplier, superseded_by__isnull=True).aggregate(value=Sum('amount'))['value'] or Decimal(0)
        opening = actual + known_cost
        if opening:
            BalanceMovement.objects.create(supplier=supplier, delta=opening, kind='opening',
                                          reason=f'Первый снимок, сообщение {message.pk}')
    expected = None if uncertain else expected_balance(supplier)
    credits = supplier.movements.exclude(kind__in=['sale', 'reversal']).aggregate(value=Sum('delta'))['value'] or Decimal(0)
    purchases = SupplierPurchase.objects.filter(order__supplier=supplier, superseded_by__isnull=True).aggregate(value=Sum('amount'))['value'] or Decimal(0)
    observation = BalanceObservation.objects.create(supplier=supplier, message=message, balance=actual,
        expected=expected, difference=actual - expected if expected is not None else None, uncertain=uncertain,
        credits_snapshot=credits, purchases_snapshot=purchases)
    # Баланс внутри чек-листа — часть заказа. Он остаётся в сверке, но не создаёт
    # второе финансовое уведомление и никогда не служит основанием пополнения.
    from .reconciliation import standalone, enqueue_observation
    if standalone(observation) and (parsed.get('topup_receipt') or observation.difference or uncertain):
        enqueue_observation(observation)


def _order_for(message, parsed):
    numbers = parsed.get('numbers', [])
    ids = set(OrderReference.objects.filter(supplier=message.supplier, number__in=numbers).values_list('order_id', flat=True))
    # Версии одного сообщения принадлежат тому же заказу, даже если поставщик
    # заменил номера. При пересечении с другой записью нужна явная проверка.
    ids.update(SupplierMessage.objects.filter(supplier=message.supplier, chat_id=message.chat_id,
        message_id=message.message_id, order__isnull=False).values_list('order_id', flat=True))
    reply = parsed.get('reply_to_message_id')
    if reply:
        replied = SupplierMessage.objects.filter(supplier=message.supplier, chat_id=message.chat_id,
            message_id=reply, order__isnull=False)
        # Ответ может продолжать старую переписку о другом заказе. При явных
        # номерах используем reply только при совпадении номера поставщика.
        if numbers:
            replied = replied.filter(order__references__number__in=numbers)
        ids.update(replied.values_list('order_id', flat=True))
    if len(ids) > 1:
        for order in DigitalOrder.objects.filter(pk__in=ids):
            _issue(order, 'Набор номеров пересекает несколько существующих заказов')
        return None
    order = (DigitalOrder.objects.select_for_update().get(pk=next(iter(ids))) if ids else
             DigitalOrder.objects.create(supplier=message.supplier))
    known = set(order.references.values_list('number', flat=True))
    if order.sale_id and known and set(numbers) - known:
        _issue(order, 'Новая группа пересекается с уже оформленной продажей; требуется ручное связывание')
        return None
    for number in numbers:
        OrderReference.objects.get_or_create(supplier=message.supplier, number=number, defaults={'order': order})
    return order


def _goods_matches(order, parsed):
    count = parsed.get('group_count', 1)
    if count > 1:
        references = set(order.references.values_list('number', flat=True))
        numbered = [str(row.get('number') or '') for row in order.items if row.get('number')]
        # Сервисная строка «Новый аккаунт» не имеет своего номера заказа и не
        # увеличивает количество выданных комплектов. Все номера должны совпасть.
        return count == len(references) == len(numbered) and set(numbered) == references
    return len(order.items) == 1 or set(parsed.get('numbers', [])) == set(order.references.values_list('number', flat=True))


def _item_signature(items):
    return sorted((row['name'], money(row['cost'])) for row in items)


def _apply(message, parsed):
    order = _order_for(message, parsed)
    if order is None:
        return None
    message.order = order
    message.save(update_fields=['order'])
    if order.source == 'api_v2':
        AuditEvent.objects.create(order=order, message=message, kind='api_message_linked')
        return order
    if order.processing_stopped:
        return order
    if parsed['kind'] == 'checklist':
        issues = list(parsed['issues'])
        if order.checklist_received:
            before = _item_signature(order.items)
            after = _item_signature(parsed['items'])
            if before != after or order.cost != money(parsed['total'] or 0):
                _issue(order, 'Получены изменённые закупочные данные; подтверждённые снимки не заменены')
            return order
        order.items = parsed['items']
        order.cost = money(parsed['total'] or 0)
        order.checklist_received = not issues
        order.save(update_fields=['items', 'cost', 'checklist_received', 'updated_at'])
        if not issues and not parsed.get('unverified_forward'):
            SupplierPurchase.objects.get_or_create(order=order, defaults={'message': message, 'amount': order.cost, 'occurred_at': message.occurred_at})
        elif issues:
            _issue(order, '; '.join(issues))
        # Готовность могла прийти раньше чек-листа: проверяем фактический состав без арифметики номеров.
        goods = list(order.messages.filter(kind='goods'))
        if goods:
            if all(_goods_matches(order, row.parsed) for row in goods):
                order.goods_received = True
                order.save(update_fields=['goods_received'])
            else:
                _issue(order, 'Готовность не совпадает с количеством/номерами группы')
    elif parsed['kind'] == 'goods':
        if order.checklist_received and not _goods_matches(order, parsed):
            _issue(order, 'Неоднозначная группа готовности; проверьте состав')
        else:
            order.goods_received = True
            order.save(update_fields=['goods_received'])
    if parsed.get('unverified_forward'):
        _issue(order, 'Пересылка без проверяемого исходного автора требует проверки')
    _refresh(order, notify=False)
    AuditEvent.objects.create(order=order, message=message, kind='supplier_' + parsed['kind'])
    return order


@retry_database_lock
@transaction.atomic
@sensitive_variables()
def accept_update(update, *, owner=None):
    if not isinstance(update, dict) or type(update.get('update_id')) is not int or not 0 <= update['update_id'] < 2**63:
        return None
    bot = DigitalBot.objects.select_for_update().get(pk=1)
    if not bot.enabled or (owner is not None and (bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now())):
        return None
    if update['update_id'] < bot.next_update_id:
        return None
    source = update.get('edited_message') or update.get('message')
    # Offset подтверждается только вместе с успешно сохранённым событием/осознанным игнорированием.
    def acknowledge():
        bot.next_update_id = update['update_id'] + 1
        bot.save(update_fields=['next_update_id', 'last_chat_id', 'bot_messages', 'human_messages', 'forwarded_messages'])
    from digital_shop.telegram import ingest as ingest_shop
    if ingest_shop(update):
        acknowledge()
        return None
    from .chat_balances import ingest_chat_update
    if ingest_chat_update(update):
        acknowledge()
        return None
    if not isinstance(source, dict):
        acknowledge()
        return None
    chat, sender = source.get('chat', {}), source.get('from', {})
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        acknowledge()
        return None
    chat_id, sender_id = chat.get('id'), sender.get('id')
    if type(chat_id) is not int or type(sender_id) is not int or chat.get('type') not in ('group', 'supergroup'):
        acknowledge()
        return None
    candidates = [row for row in Supplier.objects.select_for_update() if chat_id in row.chat_ids]
    supplier = candidates[0] if len(candidates) == 1 else None
    if not supplier or sender_id not in supplier.sender_ids:
        acknowledge()
        return None
    bot.last_chat_id = chat_id
    bot.bot_messages += bool(sender.get('is_bot'))
    bot.human_messages += not bool(sender.get('is_bot'))
    forwarded = isinstance(source.get('forward_origin'), dict)
    bot.forwarded_messages += forwarded
    text = source.get('text', source.get('caption', ''))
    parsed = parse(text)
    if not parsed and (source.get('document') or source.get('photo') or text):
        reply = source.get('reply_to_message')
        reply_id = reply.get('message_id') if isinstance(reply, dict) else None
        known = SupplierMessage.objects.filter(chat_id=chat_id, message_id=reply_id,
                    order__isnull=False).select_related('order').order_by('-edit_version').first() if type(reply_id) is int else None
        if known:
            numbers = list(known.order.references.values_list('number', flat=True))
            if numbers and isinstance(text, str) and len(text) <= 32768:
                # Reply с данными не равен подтверждению готовности: даже «завтра
                # сделаем» может быть ответом на чек-лист. Готовность даёт только
                # явное сообщение поставщика либо ручная проверка сотрудника.
                parsed = {'kind': 'data', 'balance': None, 'numbers': numbers, 'group_count': 1}
    if not parsed:
        acknowledge()
        return None
    origin = source.get('forward_origin') if forwarded else {}
    stamp = origin.get('date') or source.get('date')
    if (type(stamp) is not int or type(source.get('message_id')) is not int
            or not 0 < stamp < 253402300799 or not 0 < source['message_id'] < 2**63):
        acknowledge()
        return None
    occurred = datetime.fromtimestamp(stamp, tz=dt_timezone.utc)
    reply = source.get('reply_to_message')
    parsed['reply_to_message_id'] = reply.get('message_id') if isinstance(reply, dict) else None
    original_sender, original_chat = origin.get('sender_user'), origin.get('chat')
    origin_id = ((original_sender.get('id') if isinstance(original_sender, dict) else None)
                 or (original_chat.get('id') if isinstance(original_chat, dict) else None))
    parsed['unverified_forward'] = forwarded and origin_id not in supplier.sender_ids
    file = source.get('document')
    if not file and isinstance(source.get('photo'), list) and source['photo']:
        file = source['photo'][-1]
    file = file if isinstance(file, dict) else None
    payload = {'text': text, 'forward_origin': origin, 'attachments': []}
    if file:
        if not isinstance(file.get('file_id'), str) or (file.get('file_size') is not None and type(file['file_size']) is not int):
            acknowledge()
            return None
        payload['file'] = {key: file.get(key) for key in ('file_id', 'file_unique_id', 'file_size', 'file_name', 'mime_type')}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    duplicate = SupplierMessage.objects.filter(supplier=supplier, chat_id=chat_id, fingerprint=fingerprint).first()
    if duplicate:
        acknowledge()
        return duplicate.order
    version = source.get('edit_date', 0)
    if type(version) is not int or version < 0:
        acknowledge()
        return None
    previous = SupplierMessage.objects.filter(chat_id=chat_id, message_id=source['message_id']).order_by('-edit_version', '-pk').first()
    if SupplierMessage.objects.filter(chat_id=chat_id, message_id=source['message_id'], edit_version=version).exists():
        acknowledge()
        return None
    event = SupplierMessage.objects.create(supplier=supplier, chat_id=chat_id, message_id=source['message_id'],
        edit_version=version, sender_id=sender_id, occurred_at=occurred, forwarded=forwarded, kind=parsed['kind'],
        fingerprint=fingerprint, encrypted_payload=encrypt(payload), parsed=parsed,
        attachment_state='pending' if file else 'none')
    order = _apply(event, parsed) if parsed['kind'] != 'balance' else None
    if order is None and parsed['kind'] == 'balance' and parsed.get('reply_to_message_id'):
        linked = SupplierMessage.objects.filter(supplier=supplier, chat_id=chat_id,
            message_id=parsed['reply_to_message_id'], order__isnull=False).select_related('order').first()
        if linked and linked.order.processing_stopped:
            order = linked.order
            event.order = order
            event.save(update_fields=['order'])
    if order and order.processing_stopped:
        if file:
            event.attachment_state = 'ignored'
            event.save(update_fields=['attachment_state'])
        acknowledge()
        return order
    if previous and order and not _same_checklist_snapshot(previous.parsed, parsed):
        _issue(order, 'Сообщение отредактировано поставщиком; требуется проверка')
    if order:
        _clear_resolved_status_warnings(order, parsed)
    if file and order:
        _issue(order, 'Ожидается безопасное сохранение вложения')
    late = supplier.observations.filter(message__occurred_at__gt=occurred).exists()
    _observation(event, parsed, late=late)
    if parsed.get('topup_receipt') and parsed.get('balance') is None:
        from .notifications import enqueue_alert
        enqueue_alert(f'supplier_topup:{event.pk}',
            '💳 Получено сообщение о пополнении счёта поставщика, но новый баланс не распознан. '
            'Автоматическое зачисление заблокировано. Проверьте сообщение и баланс в CRM.')
    if order:
        _refresh(order)
    acknowledge()
    return order


@sensitive_variables()
def store_manual_goods(order, text, actor, message_key=None):
    if len(text) > 32768:
        raise ValidationError('Данные товара слишком велики.')
    from .services import _key
    message_id = _key(message_key).int % (2**63 - 1)
    if SupplierMessage.objects.filter(chat_id=0, message_id=message_id).exists():
        return
    SupplierMessage.objects.create(supplier=order.supplier, order=order, chat_id=0, message_id=message_id,
        kind='goods', occurred_at=timezone.now(), fingerprint=hashlib.sha256(text.encode()).hexdigest(),
        encrypted_payload=encrypt({'text': text, 'attachments': []}))
    AuditEvent.objects.create(order=order, actor=actor, kind='manual_goods_saved')


@retry_database_lock
@transaction.atomic
def resolve_order(*, actor, order_id, revision, reason):
    from .services import require, _version
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    order = DigitalOrder.objects.select_for_update().get(pk=order_id)
    if order.source == 'api_v2':
        raise ValidationError('Этот заказ проверяется в панели цифрового магазина.')
    _version(order, revision)
    if not str(reason or '').strip():
        raise ValidationError('Укажите причину проверки.')
    from .services import normalized_items
    rows = normalized_items(order.items)
    if not order.checklist_received or not order.goods_received or sum((money(row['cost']) for row in rows), Decimal(0)) != order.cost:
        raise ValidationError('Не хватает подтверждённого чек-листа/готовности или суммы расходятся.')
    if order.messages.filter(attachment_state__in=['pending', 'error']).exists():
        raise ValidationError('Сначала сохраните вложения.')
    order.review_reason = ''
    order.save(update_fields=['review_reason'])
    AuditEvent.objects.create(order=order, actor=actor, kind='review_resolved', detail=reason[:500])
    if not SupplierPurchase.objects.filter(order=order).exists():
        SupplierPurchase.objects.create(order=order, message=order.messages.filter(kind='checklist').first(),
                                       amount=order.cost, occurred_at=timezone.now())
    _refresh(order)
    return order


@retry_database_lock
@transaction.atomic
def confirm_fulfillment(*, actor, order_id, revision):
    """Подтверждение сотрудника без ожидания сообщения и без новой закупки API."""
    from .services import require, _version, normalized_items
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    source = DigitalOrder.objects.get(pk=order_id)
    Supplier.objects.select_for_update().get(pk=source.supplier_id)
    order = DigitalOrder.objects.select_for_update().get(pk=source.pk)
    _version(order, revision)
    if order.source == 'api_v2' or order.sale_id:
        raise ValidationError('Подтверждение доступно только входящему заказу до создания продажи; API-заказ проверяется в магазине.')
    if not order.checklist_received or order.review_reason:
        raise ValidationError('Сначала подтвердите корректность чек-листа и устраните замечания.')
    rows = normalized_items(order.items)
    if sum((money(row['cost']) for row in rows), Decimal(0)) != order.cost:
        raise ValidationError('Сумма состава не совпадает с итогом заказа.')
    purchase = SupplierPurchase.objects.filter(order=order, superseded_by__isnull=True).first()
    if not purchase or purchase.amount != order.cost:
        raise ValidationError('Сначала подтвердите корректный расход поставщика по чек-листу.')
    if order.messages.filter(attachment_state__in=['pending', 'error']).exists():
        raise ValidationError('Сначала сохраните вложения или разрешите ошибку их получения.')
    if order.goods_received:
        return order
    order.goods_received = True
    order.save(update_fields=['goods_received', 'updated_at'])
    AuditEvent.objects.create(order=order, actor=actor, kind='fulfillment_confirmed_manually',
                              detail='Сотрудник подтвердил выполнение услуги без сообщения готовности в чате')
    _refresh(order)
    return order


@retry_database_lock
@transaction.atomic
def link_orders(*, actor, source_id, target_id, revision, reason):
    """Явная привязка готовности/ручной продажи; закупочные снимки Sale не перезаписываются."""
    from .services import require, _version, record_id
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    source_id, target_id = record_id(source_id), record_id(target_id)
    if str(source_id) == str(target_id) or not str(reason or '').strip():
        raise ValidationError('Выберите другой заказ и причину связывания.')
    rows = {row.pk: row for row in DigitalOrder.objects.select_for_update().filter(pk__in=[source_id, target_id]).order_by('pk')}
    if len(rows) != 2:
        raise ValidationError('Цифровой заказ для связывания не найден.')
    source, target = rows[int(source_id)], rows[int(target_id)]
    if source.source == 'api_v2' or target.source == 'api_v2':
        raise ValidationError('Закупки магазина нельзя объединять с импортированными сообщениями.')
    _version(source, revision)
    if target.processing_stopped:
        raise ValidationError('Нельзя привязать сообщения к отменённому заказу.')
    if source.supplier_id != target.supplier_id or source.sale_id:
        raise ValidationError('Источник уже оформлен либо принадлежит другому поставщику.')
    if source.checklist_received and target.checklist_received and (_item_signature(source.items) != _item_signature(target.items) or source.cost != target.cost):
        raise ValidationError('Составы различаются; автоматическое объединение запрещено.')
    if source.checklist_received and not target.checklist_received:
        target.items, target.cost, target.checklist_received = source.items, source.cost, True
    for ref in source.references.all():
        ref.order = target
        ref.save(update_fields=['order'])
    for event in source.messages.all():
        event.order = target
        event.save(update_fields=['order'])
    target.goods_received = target.goods_received or source.goods_received
    target.save(update_fields=['items', 'cost', 'checklist_received', 'goods_received'])
    purchase = SupplierPurchase.objects.filter(order=source).first()
    if purchase and not SupplierPurchase.objects.filter(order=target).exists():
        purchase.order = target
        purchase.save(update_fields=['order'])
    elif purchase:
        # Сотрудник явно подтвердил совпадающие составы: сохраняем обе исходные
        # записи, но одну отмечаем как дубликат для контрольного расчёта.
        target_purchase = SupplierPurchase.objects.get(order=target)
        if purchase.amount != target_purchase.amount:
            raise ValidationError('Закупки отличаются по сумме; объединение не выполнено.')
        purchase.superseded_by = target_purchase
        purchase.save(update_fields=['superseded_by'])
    source.review_reason = f'Связан с заказом №{target.pk}'
    source.state, source.revision = DigitalOrder.State.REVIEW, source.revision + 1
    source.save(update_fields=['review_reason', 'state', 'revision', 'updated_at'])
    AuditEvent.objects.create(order=target, actor=actor, kind='orders_linked', detail=f'source={source.pk}; {reason[:350]}')
    _refresh(target)
    return target


@retry_database_lock
@transaction.atomic
def correct_checklist(*, actor, order_id, revision, items, reason, goods_confirmed=False):
    """Явная проверка неоднозначного источника, только до создания Sale."""
    from .services import require, normalized_items, _version
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    source = DigitalOrder.objects.get(pk=order_id)
    if source.source == 'api_v2':
        raise ValidationError('Подтверждённые данные API-заказа нельзя заменить чек-листом.')
    Supplier.objects.select_for_update().get(pk=source.supplier_id)
    order = DigitalOrder.objects.select_for_update().get(pk=order_id)
    _version(order, revision)
    if order.sale_id or not str(reason or '').strip():
        raise ValidationError('Подтверждённую Sale не переписываем; для исправления нужна причина.')
    rows = normalized_items(items)
    for row in rows:
        if row['number']:
            ref, _ = OrderReference.objects.get_or_create(supplier=order.supplier, number=row['number'], defaults={'order': order})
            if ref.order_id != order.pk:
                raise ValidationError('Номер уже принадлежит другому цифровому заказу.')
    before = order.cost
    order.items, order.cost, order.checklist_received = rows, sum((money(r['cost']) for r in rows), Decimal(0)), True
    order.goods_received = order.goods_received or goods_confirmed
    order.review_reason = ''
    order.save(update_fields=['items', 'cost', 'checklist_received', 'goods_received', 'review_reason'])
    purchase, created = SupplierPurchase.objects.get_or_create(order=order, defaults={'amount': order.cost, 'occurred_at': timezone.now()})
    if not created and purchase.amount != order.cost:
        purchase.amount = order.cost
        purchase.save(update_fields=['amount'])
    AuditEvent.objects.create(order=order, actor=actor, kind='checklist_corrected', detail=f'cost={before} -> {order.cost}; {reason[:350]}')
    _refresh(order)
    return order


@retry_database_lock
@transaction.atomic
def attach_message(*, actor, order_id, message_id, revision, reason):
    from .services import require, _version, record_id
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    order = DigitalOrder.objects.select_for_update().get(pk=order_id)
    _version(order, revision)
    message = SupplierMessage.objects.select_for_update().filter(pk=record_id(message_id)).first()
    if message is None:
        raise ValidationError('Сообщение не найдено.')
    if message.order_id or message.supplier_id != order.supplier_id or not str(reason or '').strip():
        raise ValidationError('Выберите несвязанное сообщение этого поставщика и укажите причину.')
    message.order = order
    message.save(update_fields=['order'])
    if message.kind == 'goods' and not order.sale_id:
        order.goods_received = True
        order.save(update_fields=['goods_received'])
    _issue(order, 'Сообщение связано вручную; проверьте комплект и себестоимость')
    AuditEvent.objects.create(order=order, message=message, actor=actor, kind='message_attached', detail=reason[:500])
    return order
