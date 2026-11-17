"""Возобновляемое исполнение: намерение до POST, неизвестный исход не равен отказу."""
from datetime import timedelta
from decimal import Decimal
import json
import hashlib
import re
import uuid
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from core.db_retry import retry_database_lock
from digital_prices.api import amount, APIError
from digital_prices.models import Integration
from digital_prices.provider import ProviderClient, wire
from digital_sales.crypto import encrypt, decrypt
from digital_sales.models import (BuyerBalanceChat, DigitalOrder, SupplierPurchase,
    OrderReference, BalanceMovement, DigitalBot)
from .models import ShopConfig, ShopChat, PurchaseIntent, BalanceHold, ResultDelivery, AuditEvent, Cart, CartLine
from .services import write_lock, allocated
from .public import result_dto, checked


def alert(intent, category):
    from digital_sales.notifications import enqueue_alert
    enqueue_alert(f'shop:{intent.pk}:{category}',
        f'Цифровой магазин: заказ {intent.pk.hex[:8]} требует проверки. Категория: {category}. '
        'Повторная покупка под новым идентификатором заблокирована. Откройте сверку магазина в CRM.')


def customer_notice(intent, *, failed=False):
    from digital_sales.models import BalanceChatPublication
    binding = BuyerBalanceChat.objects.filter(pk=intent.cart.chat_id, buyer_id=intent.cart.buyer_id).first()
    if binding is None:
        return
    text = (f'Заказ GameBAT {intent.pk.hex[:8]} не был оформлен. Резерв освобождён.' if failed else
        f'Заказ GameBAT {intent.pk.hex[:8]} уточняется. Не оформляйте его повторно. '
        'Статус и доступный баланс можно посмотреть через /shop; при необходимости обратитесь к @GameBAT_Store.')
    BalanceChatPublication.objects.get_or_create(event_key=f'shop:{intent.pk}:{"failed" if failed else "review"}', defaults={
        'chat': binding, 'buyer_id': intent.cart.buyer_id, 'text': checked(text), 'generated_at': timezone.now()})


def reprice_after_rejection(intent):
    """Только документированный отказ до закупки; новый POST потребует нового согласия клиента."""
    hold = BalanceHold.objects.select_for_update().get(intent=intent)
    if intent.external_order_id or intent.lines.exclude(purchase_id='').exists():
        raise APIError('rejection_conflict')
    hold.remaining, hold.state = Decimal(0), 'released'
    hold.save(update_fields=['remaining', 'state'])
    old = intent.cart
    cart = Cart.objects.filter(chat=old.chat, buyer=old.buyer).exclude(state='closed').first()
    if cart is None:
        cart = Cart.objects.create(chat=old.chat, buyer=old.buyer, telegram_user_id=old.telegram_user_id,
                                   menu_message_id=old.menu_message_id)
    if cart.state == 'open' and not cart.lines.exists():
        # После подтверждения меню уже могло открыть следующую общую корзину.
        # Возвращаем отклонённый состав только в пустой черновик, без реквизитов.
        for line in old.lines.order_by('pk'):
            CartLine.objects.create(cart=cart, product=line.product, quantity=line.quantity,
                account_key='a' + uuid.uuid4().hex[:10] if line.account_key else '',
                account_mode=line.account_mode, parameters=line.parameters)
        from .services import invalidate
        invalidate(cart)
    intent.state, intent.finished_at, intent.encrypted_body = 'failed', timezone.now(), ''
    from digital_sales.models import BalanceChatPublication
    BalanceChatPublication.objects.get_or_create(event_key=f'shop:{intent.pk}:reprice', defaults={
        'chat': old.chat, 'buyer': old.buyer, 'generated_at': timezone.now(),
        'text': checked('🧾 Расчёт изменился или истёк до оформления. Покупка не создана, резерв освобождён. '
                        'Откройте корзину в меню группы, проверьте состав и подтвердите новый расчёт.')})
    AuditEvent.objects.create(intent=intent, kind='reprice_required')


@retry_database_lock
@transaction.atomic
def claim():
    write_lock()
    now = timezone.now()
    row = PurchaseIntent.objects.select_for_update().filter(state__in=['queued', 'submitting', 'uncertain', 'processing'], next_at__lte=now).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)).order_by('next_at', 'created_at').first()
    if row is None:
        return None
    if row.state == 'submitting':
        row.state = 'uncertain'  # Процесс мог умереть после отправки POST.
    row.owner, row.lease_until = uuid.uuid4(), now + timedelta(minutes=3)
    row.save(update_fields=['owner', 'lease_until', 'state'])
    return row


def current(intent):
    row = PurchaseIntent.objects.select_for_update().get(pk=intent.pk)
    if row.owner != intent.owner or not row.lease_until or row.lease_until <= timezone.now():
        raise ValidationError('Аренда обработки потеряна.')
    return row


def heartbeat(intent, renew):
    renew()
    with transaction.atomic():
        stored = current(intent)
        stored.lease_until = timezone.now() + timedelta(minutes=3)
        stored.save(update_fields=['lease_until'])


def poll_orders(*, renew=lambda: None):
    """Один список на все активные закупки; подробный ответ нужен при изменении состояния."""
    if not PurchaseIntent.objects.filter(state='processing').exclude(external_order_id='').exists():
        return False
    with transaction.atomic():
        write_lock()
        config = ShopConfig.objects.select_for_update().get(pk=1)
        if config.list_poll_at and config.list_poll_at > timezone.now() - timedelta(seconds=12):
            return False
        config.list_poll_at = timezone.now()
        config.save(update_fields=['list_poll_at'])
    integration = Integration.objects.filter(pk=1, enabled=True).first()
    if integration is None or not integration.encrypted_key:
        return False
    from integrations.crypto import decrypt_secret
    client = ProviderClient(decrypt_secret(integration.encrypted_key), heartbeat=renew)
    try:
        response = client.orders(page=config.list_page)
        rows = response.get('orders')
        if not isinstance(rows, list) or type(response.get('has_more')) is not bool:
            raise APIError('invalid_order_list')
        with transaction.atomic():
            for data in rows:
                if not isinstance(data, dict):
                    raise APIError('invalid_order_list')
                row = PurchaseIntent.objects.select_for_update().filter(external_order_id=data.get('order_id'), state='processing').first()
                if row is None:
                    continue
                # В списке нет результатов выдачи: сравниваем лишь состояние, деньги и идентичности строк.
                stamp = {'status': data.get('status'), 'completed': data.get('completed'),
                         'charged_total': data.get('charged_total'), 'items': [
                             {k: item.get(k) for k in ('line_id', 'purchase_id', 'status', 'paid')}
                             for item in data.get('items', []) if isinstance(item, dict)]}
                digest = hashlib.sha256(wire(stamp).encode()).hexdigest()
                if row.poll_fingerprint != digest:
                    row.poll_fingerprint, row.next_at = digest, timezone.now()
                    row.save(update_fields=['poll_fingerprint', 'next_at'])
            config.list_page = config.list_page + 1 if response['has_more'] and config.list_page < 1000 else 1
            config.save(update_fields=['list_page'])
    except APIError as exc:
        config.error_category = exc.category
        config.save(update_fields=['error_category'])
    finally:
        client.close()
    return True


def _validate_order(response, intent):
    if (not isinstance(response, dict) or response.get('client_order_id') != intent.client_order_id or
            response.get('currency', '').upper() != 'RUB' or not isinstance(response.get('order_id'), str) or
            not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', response['order_id'])):
        raise APIError('invalid_order')
    if intent.external_order_id and intent.external_order_id != response['order_id']:
        raise APIError('order_identity_conflict')
    rows = response.get('items')
    if not isinstance(rows, list) or len(rows) > 30 or any(not isinstance(v, dict) for v in rows):
        raise APIError('invalid_order')
    ids = [v.get('line_id') for v in rows]
    expected = set(intent.lines.values_list('line_id', flat=True))
    if len(set(ids)) != len(ids) or set(ids) - expected:
        raise APIError('invalid_order')
    charged = amount(response.get('charged_total'))
    if sum((amount(v.get('price')) for v in rows), Decimal(0)) != charged:
        raise APIError('charge_unconfirmed')
    if amount(response.get('quoted_total')) != intent.cart.quoted_total:
        raise APIError('quote_mismatch')
    for row in rows:
        if row.get('currency', '').upper() != 'RUB' or type(row.get('purchase_id')) is not int or row['purchase_id'] <= 0:
            raise APIError('invalid_order')
    return rows


def finalize_line(line, result, actor):
    """Один путь проведения для worker и явно проверенного сотрудником результата."""
    from digital_sales.services import confirm_order, complete_sale
    if line.settled_at:
        return
    if line.status not in ('completed', 'active') or line.confirmed_cost is None:
        raise ValidationError('Внешнее выполнение пока не подтверждено.')
    parts = result_dto(result, name=line.snapshot['name'], quantity=line.snapshot['quantity'], completed=True).parts()
    line.encrypted_result = encrypt({'parts': parts})
    line.save(update_fields=['encrypted_result'])
    order = line.digital_order
    order.state, order.goods_received = DigitalOrder.State.READY, True
    order.save(update_fields=['state', 'goods_received'])
    sale = confirm_order(actor=actor, order_id=order.pk, revision=order.revision)
    complete_sale(actor=actor, sale_id=sale.pk)
    ResultDelivery.objects.get_or_create(line=line, defaults={'buyer_id': line.intent.cart.buyer_id,
        'chat_id': line.intent.cart.chat_id, 'encrypted_text': line.encrypted_result})


@sensitive_variables()
@retry_database_lock
@transaction.atomic
def reconcile(intent, response):
    write_lock()
    intent = current(intent)
    rows = _validate_order(response, intent)
    config = ShopConfig.objects.get(pk=1)
    from digital_sales.services import require
    actor = require(config.actor, 'digital_sales.create_digital_sales', 'sales.create_sale',
        'digital_sales.complete_digital_sales', 'sales.mark_sale_paid')
    intent.external_order_id = response['order_id']
    intent.encrypted_response = encrypt(json.loads(wire(response), parse_float=str))
    issues = ['charge_exceeds_quote'] if amount(response['charged_total']) > intent.cart.quoted_total else []
    if response.get('status') not in ('accepted', 'processing', 'partial', 'completed', 'finished', 'failed'):
        issues.append('unknown_order_status')
    for row in rows:
        line = intent.lines.select_for_update().select_related('cart_line').get(line_id=row['line_id'])
        purchase_id = str(row['purchase_id'])
        confirmed_cost = amount(row['price'])
        if line.purchase_id and line.purchase_id != purchase_id:
            raise APIError('purchase_identity_conflict')
        if line.confirmed_cost is not None and line.confirmed_cost != confirmed_cost:
            raise APIError('charge_changed')
        if line.digital_order_id is None:
            # Сообщение от поставщика могло прийти раньше ответа POST. Не создаём второй учёт.
            if OrderReference.objects.filter(supplier_id=config.supplier_id, number=purchase_id).exists():
                raise APIError('purchase_already_imported')
            order = DigitalOrder.objects.create(supplier_id=config.supplier_id, buyer_id=intent.cart.buyer_id,
                source='api_v2', state=DigitalOrder.State.GOODS, price=line.client_price, cost=confirmed_cost,
                items=[{'name': line.snapshot['name'], 'cost': str(share), 'number': ''}
                       for share in allocated(confirmed_cost, [Decimal(1)] * line.snapshot['quantity'])],
                checklist_received=True, goods_received=False, edited_by=actor)
            OrderReference.objects.create(supplier_id=config.supplier_id, order=order, number=purchase_id)
            SupplierPurchase.objects.create(order=order, amount=confirmed_cost, occurred_at=timezone.now())
            line.digital_order = order
            if confirmed_cost:
                line.supplier_movement = BalanceMovement.objects.create(supplier_id=config.supplier_id, delta=-confirmed_cost,
                    kind='sale', actor=actor, reason=f'Цифровая закупка №{order.pk}',
                    operation_key=uuid.uuid5(intent.pk, 'supplier:' + line.line_id))
        line.purchase_id, line.confirmed_cost = purchase_id, confirmed_cost
        status = row.get('status')
        line.status = status if status in ('queued', 'processing', 'completed', 'active', 'cancelled') else 'unknown'
        if line.status == 'unknown':
            issues.append('unknown_status')
        if line.status == 'cancelled':
            # Отменённая внешняя строка сама по себе не доказывает возврат закупки.
            issues.append('refund_unconfirmed')
        line.save()
        if line.status in ('completed', 'active') and line.settled_at is None:
            if 'charge_exceeds_quote' in issues or 'unknown_order_status' in issues:
                continue
            try:
                finalize_line(line, row.get('result'), actor)
            except ValidationError:
                issues.append('result_review')
                continue
    unconfirmed = response.get('unconfirmed_items')
    if not isinstance(unconfirmed, list):
        raise APIError('invalid_order')
    if unconfirmed or response.get('status') in ('partial', 'processing') and len(rows) != intent.lines.count():
        issues.append('partial_unconfirmed')
    if response.get('status') not in ('accepted', 'processing', 'partial', 'completed', 'finished', 'failed'):
        issues.append('unknown_order_status')
    failed = response.get('status') == 'failed' and not rows and not unconfirmed and amount(response.get('charged_total')) == 0
    if failed:
        # Единственный автоматический возврат всего резерва: доказано, что ни одной закупки нет.
        hold = BalanceHold.objects.select_for_update().get(intent=intent)
        hold.remaining, hold.state = Decimal(0), 'released'
        hold.save(update_fields=['remaining', 'state'])
        intent.state, intent.finished_at = 'failed', timezone.now()
        customer_notice(intent, failed=True)
    elif issues:
        intent.state, intent.error_category = 'review', issues[0]
        alert(intent, issues[0])
        customer_notice(intent)
    elif intent.lines.filter(settled_at__isnull=True).exists():
        intent.state = 'processing'
    else:
        intent.state, intent.finished_at = 'done', timezone.now()
    if intent.finished_at:
        intent.encrypted_body = ''  # Запрос больше не повторяется; реквизиты удаляются из намерения.
        intent.cart.encrypted_credentials = ''
        intent.cart.save(update_fields=['encrypted_credentials'])
    intent.owner, intent.lease_until = None, None
    # Общий список замечает изменения каждые 12 секунд; резервный индивидуальный опрос — раз в 2 минуты.
    intent.next_at = timezone.now() + timedelta(seconds=120)
    intent.save()
    AuditEvent.objects.create(kind='order_reconciled', intent=intent, detail={'state': intent.state, 'lines': len(rows)})


def process_one(*, client_factory=ProviderClient, renew=lambda: None):
    config = ShopConfig.objects.filter(pk=1).first()
    integration = Integration.objects.filter(pk=1, enabled=True).first()
    # Выключение магазина не бросает уже созданные закупки без сверки.
    if not config or not integration or not integration.encrypted_key:
        return False
    intent = claim()
    if intent is None:
        return False
    from integrations.crypto import decrypt_secret
    client = client_factory(decrypt_secret(integration.encrypted_key), heartbeat=lambda: heartbeat(intent, renew))
    try:
        if intent.state == 'queued':
            if not config.enabled or not config.purchases_enabled:
                raise APIError('purchases_disabled')
            with transaction.atomic():
                stored = current(intent)
                stored.state, stored.attempts = 'submitting', stored.attempts + 1
                stored.save(update_fields=['state', 'attempts'])
            serialized = decrypt(intent.encrypted_body)['wire']
            if hashlib.sha256(serialized.encode()).hexdigest() != intent.body_hash:
                raise APIError('body_hash_mismatch')
            response = client.purchase(serialized)
        elif intent.external_order_id:
            response = client.order(intent.external_order_id)
        else:
            found = client.orders(client_order_id=intent.client_order_id)
            matches = found.get('orders')
            if not isinstance(matches, list) or len(matches) > 1:
                raise APIError('lookup_ambiguous')
            if not matches:
                # Стабильный ID и неизменяемое тело — даже после потери ответа.
                if not config.enabled or not config.purchases_enabled:
                    raise APIError('purchases_disabled')
                serialized = decrypt(intent.encrypted_body)['wire']
                if hashlib.sha256(serialized.encode()).hexdigest() != intent.body_hash:
                    raise APIError('body_hash_mismatch')
                response = client.purchase(serialized)
            else:
                response = client.order(matches[0]['order_id'])
        reconcile(intent, response)
        config.last_poll_at = config.last_success_at = timezone.now()
        config.error_category = ''
        config.save(update_fields=['last_poll_at', 'last_success_at', 'error_category'])
    except (APIError, ValidationError, PermissionDenied, KeyError) as exc:
        category = exc.category if isinstance(exc, APIError) else 'reconciliation_review'
        config.last_poll_at, config.error_category = timezone.now(), category
        config.save(update_fields=['last_poll_at', 'error_category'])
        with transaction.atomic():
            stored = current(intent)
            transient = category in ('network', 'network_timeout', 'upstream', 'rate_limited')
            if category in ('price_changed', 'quote_expired') and intent.state == 'queued':
                reprice_after_rejection(stored)
            else:
                stored.state = 'uncertain' if transient and not stored.external_order_id else 'processing' if transient else 'review'
            stored.error_category = category
            stored.owner, stored.lease_until = None, None
            stored.next_at = timezone.now() + timedelta(seconds=max(15, getattr(exc, 'retry_after', 0)))
            stored.save()
            alert(stored, category)
            if not transient and stored.state != 'failed':
                customer_notice(stored)
    finally:
        client.close()
    return True


def publish_result(client):
    row = ResultDelivery.objects.filter(state='queued').select_related('line__intent__cart').order_by('pk').first()
    if row is None:
        return False
    # Публикация допустима только в исходную действующую группу того же покупателя.
    if (not DigitalBot.objects.filter(pk=1, enabled=True).exists() or
            not BuyerBalanceChat.objects.filter(pk=row.chat_id, buyer_id=row.buyer_id).exists() or
            not ShopChat.objects.filter(binding_id=row.chat_id, enabled=True).exists()):
        row.state = 'review'
        row.save(update_fields=['state'])
        alert(row.line.intent, 'delivery_binding')
        return True
    from digital_sales.models import Supplier
    if any(row.chat_id in supplier.chat_ids for supplier in Supplier.objects.all()):
        row.state = 'review'
        row.save(update_fields=['state'])
        return True
    try:
        payload = decrypt(row.encrypted_text)
        parts = payload.get('parts') or [payload.get('text')]
        if not isinstance(parts, list) or not 1 <= len(parts) <= 30 or row.progress_index >= len(parts):
            raise ValidationError('Нарушен состав выдачи.')
        for part in parts:
            checked(part)
        text = parts[row.progress_index]
    except (ValidationError, KeyError, TypeError, AttributeError):
        row.state = 'review'
        row.save(update_fields=['state'])
        alert(row.line.intent, 'public_result_blocked')
        return True
    with transaction.atomic():
        stored = ResultDelivery.objects.select_for_update().get(pk=row.pk)
        if stored.state != 'queued':
            return False
        stored.state = 'sending'
        stored.save(update_fields=['state'])
    from telegram_bots.client import TelegramError
    try:
        result = client.message(row.chat_id, text)
        if not isinstance(result, dict) or type(result.get('message_id')) is not int:
            raise TelegramError('invalid_response', uncertain=True)
    except TelegramError as exc:
        # Коды не пересылаются повторно при неизвестном исходе даже после перезапуска.
        row.state = 'uncertain' if exc.uncertain else 'review'
        row.save(update_fields=['state'])
        alert(row.line.intent, 'delivery_' + row.state)
        return True
    row.message_id = result['message_id']
    row.message_ids = [*row.message_ids, result['message_id']]
    row.progress_index += 1
    row.state = 'sent' if row.progress_index == len(parts) else 'queued'
    if row.state == 'sent':
        row.sent_at, row.encrypted_text = timezone.now(), ''
    row.save(update_fields=['message_id', 'message_ids', 'progress_index', 'state', 'sent_at', 'encrypted_text'])
    return True


def recover_results():
    for row in ResultDelivery.objects.filter(state='sending').select_related('line__intent'):
        row.state = 'uncertain'
        row.save(update_fields=['state'])
        alert(row.line.intent, 'delivery_uncertain')
