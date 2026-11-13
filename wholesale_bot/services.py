"""Авторизация и адаптер штатной продажи для внешнего покупателя."""
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from sales.models import Sale
from sales.services import create_sale
from .models import BotConfig, Customer, OrderIntent, Delivery, Audit

PAUSED_MESSAGE = ('⏸ Оптовый бот временно не принимает и не обрабатывает заказы.\n\n'
                  '💬 По вопросам заказа, наличия и оплаты обратитесь к администратору: @GameBAT_Store\n\n'
                  'Спасибо за понимание! Мы сообщим, когда работа возобновится. 🙌')
RESUMED_MESSAGE = ('✅ Оптовый бот снова работает!\n\n'
                   '📋 Скачайте актуальный прайс, укажите количества и отправьте заполненный файл в этот чат.\n'
                   '💬 Нужна помощь? Администратор: @GameBAT_Store')


def require(actor, permission):
    user = get_user_model().objects.filter(pk=getattr(actor, 'pk', None), is_active=True).first()
    if not user or not user.has_perm(permission):
        raise PermissionDenied('Недостаточно прав для управления оптовым ботом.')
    return user


def operator():
    config = require_accepting()
    if (not config or not config.warehouse_id or not config.operator_id or not config.operator.is_active
            or not config.operator.has_perms(['sales.create_sale', 'sales.import_wholesale_price',
                                             'sales.view_sale_detail', 'price.generate_wholesale_price'])):
        raise ValidationError('Оформление временно недоступно. Сотрудник должен проверить настройки бота.')
    return config, config.operator


def require_accepting():
    """Внутри учётной транзакции блокирует гонку создания Sale с выключением приёма."""
    config = BotConfig.objects.select_for_update().select_related('operator', 'warehouse').filter(pk=1).first()
    if config and not config.accepting_orders:
        raise ValidationError(PAUSED_MESSAGE)
    return config


@retry_database_lock
@transaction.atomic
def set_service_state(*, actor, accepting, revision):
    actor = require(actor, 'wholesale_bot.configure_wholesale_bot')
    if type(accepting) is not bool:
        raise ValidationError('Выберите включение или выключение приёма заказов.')
    config = BotConfig.objects.select_for_update().filter(pk=1).first()
    if not config or not config.enabled:
        raise ValidationError('Сначала подключите оптового бота в настройках CRM.')
    if config.accepting_orders == accepting:
        return config
    if str(config.service_revision) != str(revision):
        raise ValidationError('Режим уже изменён другим сотрудником. Обновите панель управления.')
    config.accepting_orders = accepting
    config.service_revision += 1
    config.save(update_fields=['accepting_orders', 'service_revision'])
    Audit.objects.create(actor=actor, kind='service_resumed' if accepting else 'service_paused',
                         detail=f'revision={config.service_revision}')
    from .handlers import menu
    for customer in Customer.objects.filter(status=Customer.Status.AUTHORIZED, partner__is_archived=False):
        enqueue(customer, f'service:{config.service_revision}:{customer.pk}',
                text=RESUMED_MESSAGE if accepting else PAUSED_MESSAGE,
                markup=menu(customer, accepting=accepting))
    return config


def active_customer(customer_id, *, revision=None):
    customer = Customer.objects.select_for_update().select_related('partner').get(pk=customer_id)
    if (customer.status != Customer.Status.AUTHORIZED or not customer.partner_id or customer.partner.is_archived
            or revision is not None and customer.revision != revision):
        raise ValidationError('Для оформления заказа необходимо пройти авторизацию. Прежние файлы после перепривязки недействительны.')
    return customer


def enqueue(customer, key, *, text='', markup=None, intent=None, issue=None, public=False, document=None, filename=''):
    # Полный список дефицитов/изменений не обрезается лимитом одного сообщения Telegram.
    parts = []
    while len(text) > 3800:
        cut = text.rfind('\n', 0, 3800)
        if cut < 1900:
            cut = 3800
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    first = None
    for index, part in enumerate(parts):
        row = Delivery.objects.get_or_create(key=key if index == 0 else f'{key}:part:{index}', defaults={
            'customer': customer, 'customer_revision': customer.revision, 'text': part,
            'markup': (markup or {}) if index == len(parts) - 1 else {},
            'intent': intent, 'issue': issue, 'requires_authorization': not public,
            'document': document if index == 0 else None, 'filename': filename})[0]
        first = first or row
    return first


@retry_database_lock
@transaction.atomic
def authorize(*, actor, customer_id, revision, action, partner_id=None):
    actor = require(actor, 'wholesale_bot.manage_wholesale_customers')
    customer = Customer.objects.select_for_update().get(pk=customer_id)
    if str(customer.revision) != str(revision):
        raise ValidationError('Заявка уже изменена. Обновите страницу.')
    previous = customer.partner_id
    if action == 'approve':
        from partners.models import Partner
        try:
            partner = Partner.objects.filter(pk=int(partner_id), is_archived=False).first()
        except (TypeError, ValueError, OverflowError):
            partner = None
        if not partner:
            raise ValidationError('Выберите действующего партнёра.')
        customer.status, customer.partner = Customer.Status.AUTHORIZED, partner
        customer.approved_by, customer.approved_at = actor, timezone.now()
        customer.revoked_at = None
        text = f'Авторизация выполнена.\nВаш аккаунт привязан к партнёру: {partner.name}.\nСкачайте оптовый прайс, заполните количества и отправьте XLSX обратно.'
    elif action in ('reject', 'revoke'):
        customer.status = Customer.Status.REJECTED if action == 'reject' else Customer.Status.REVOKED
        customer.revoked_at = timezone.now()
        text = 'Заявка отклонена.' if action == 'reject' else 'Доступ отозван. Для новых заказов нужна авторизация сотрудником.'
    else:
        raise ValidationError('Неизвестное действие.')
    customer.revision += 1
    customer.save()
    Audit.objects.create(customer=customer, actor=actor, kind=action,
                         detail=f'partner={previous}->{customer.partner_id};revision={customer.revision}')
    from .handlers import menu
    enqueue(customer, f'access:{customer.pk}:{customer.revision}', text=text,
            markup=menu(customer), public=True)
    return customer


def _present(intent):
    """Сохранённая ревизия является единственным основанием callback, не присланные цены."""
    customer = intent.customer
    prefix = f'w:{intent.pk.hex}:{intent.revision}'
    markup = {}
    if intent.state == OrderIntent.State.PRICES:
        old = sum(Decimal(row.get('previous_price', source['original_price'])) * row['quantity']
                  for source, row in zip(intent.lines, intent.quote, strict=True))
        new = sum(Decimal(row['price']) * row['quantity'] for row in intent.quote)
        changes = [f"• {row['label']}: {row.get('previous_price', source['original_price'])} → {row['price']} ₽ × {row['quantity']}"
                   for source, row in zip(intent.lines, intent.quote, strict=True)
                   if Decimal(row.get('previous_price', source['original_price'])) != Decimal(row['price'])]
        text = 'Обнаружено изменение цен.\n' + '\n'.join(changes)
        text += f'\nВсего изменённых позиций: {len(changes)}.\nСтарая сумма: {old:.2f} ₽. Новая сумма: {new:.2f} ₽.'
        markup = {'inline_keyboard': [[{'text': 'Подтвердить актуальные цены', 'callback_data': prefix + ':confirm'}],
                                     [{'text': 'Отменить оформление', 'callback_data': prefix + ':cancel'}]]}
    elif intent.state == OrderIntent.State.DUPLICATE:
        sale = intent.duplicate_of.sale
        text = f'Аналогичный файл уже оформлен: {sale.visible_id}' + (' (продажа отменена).' if sale.is_cancelled else '.')
        text += '\nСоздать отдельный новый заказ на тот же состав? Наличие и цены будут проверены заново.'
        markup = {'inline_keyboard': [[{'text': 'Создать повторный заказ', 'callback_data': prefix + ':repeat'}],
                                     [{'text': 'Отменить оформление', 'callback_data': prefix + ':cancel'}]]}
    elif intent.sale_id:
        text = f'Заказ успешно создан: {intent.sale.visible_id}.\nПартнёр: {intent.sale.partner_name_snapshot}.\nСумма: {intent.sale.total_amount} ₽.\nОплата: наличные, постоплата. Ваш заказ передан в обработку.'
        enqueue(customer, f'invoice:{intent.pk}', intent=intent)
    else:
        text = intent.error or 'Оформление отменено. Можно отправить новый файл.'
    enqueue(customer, f'intent:{intent.pk}:{intent.revision}', text=text, markup=markup, intent=intent)


def _finish(intent, *, confirmed=False):
    from .documents import current_lines
    active_customer(intent.customer_id, revision=intent.customer_revision)
    _config, actor = operator()
    if intent.expires_at <= timezone.now():
        raise ValidationError('Расчёт устарел. Загрузите файл заново.')
    try:
        lines = current_lines(intent)
    except ValidationError as exc:
        detail = '; '.join(exc.messages)
        shortage = 'запрошено' in detail and 'доступно' in detail
        intent.state = OrderIntent.State.SHORTAGE if shortage else OrderIntent.State.FAILED
        intent.error = detail + ('\nИсправьте количества в Excel-файле и отправьте его повторно.'
                                if shortage else '\nОформление не выполнено. Обратитесь к сотруднику ReSOURCE.')
    else:
        quote = [{'price': row['unit_price'], 'quantity': row['quantity'], 'label': row['label']} for row in lines]
        changed = any(Decimal(row['price']) != Decimal(source['original_price'])
                      for source, row in zip(intent.lines, quote, strict=True))
        quote_changed = [row['price'] for row in quote] != [row['price'] for row in intent.quote]
        if (confirmed and quote_changed) or (not confirmed and changed):
            for index, row in enumerate(quote):
                row['previous_price'] = intent.quote[index]['price'] if confirmed else intent.lines[index]['original_price']
            intent.state, intent.quote = OrderIntent.State.PRICES, quote
        else:
            # create_sale заново блокирует товар и проверяет stock. Сеть здесь не выполняется.
            sale = create_sale(actor=actor, warehouse_id=intent.issue.warehouse_id,
                price_type=Sale.PriceType.WHOLESALE, sale_type=Sale.SaleType.WHOLESALE,
                payment_method=Sale.PaymentMethod.CASH_POSTPAY, partner_id=intent.partner_id,
                lines=lines, creation_key=intent.pk, note=f'Telegram — оптовый бот ReSOURCE; заявка {intent.pk}')
            intent.sale, intent.state, intent.quote = sale, OrderIntent.State.CREATED, quote
            if confirmed:
                intent.price_confirmed_at = timezone.now()
            Audit.objects.create(customer=intent.customer, kind='sale_created', actor=actor,
                                 detail=f'intent={intent.pk};sale={sale.pk}')
    intent.revision += 1
    intent.save()
    _present(intent)
    return intent


@retry_database_lock
@transaction.atomic
def receive_order(*, customer_id, message_id, content):
    from .documents import read_order, MAX_FILE
    require_accepting()
    customer = active_customer(customer_id)
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_FILE:
        raise ValidationError('Отправьте XLSX размером не больше 5 МБ.')
    existing = OrderIntent.objects.filter(customer=customer, message_id=message_id).first()
    if existing:
        return existing
    intent = OrderIntent.objects.create(customer=customer, partner=customer.partner,
        customer_revision=customer.revision, message_id=message_id, content=content,
        expires_at=timezone.now() + timedelta(minutes=30))
    try:
        issue, lines = read_order(content, customer)
    except ValidationError as exc:
        intent.state, intent.error = OrderIntent.State.INVALID, '; '.join(exc.messages)
        intent.save()
        _present(intent)
        return intent
    intent.issue, intent.lines = issue, lines
    intent.fingerprint = hashlib.sha256(json.dumps([str(issue.pk), lines], sort_keys=True).encode()).hexdigest()
    previous = OrderIntent.objects.filter(customer=customer, fingerprint=intent.fingerprint, sale__isnull=False).first()
    if previous:
        intent.state, intent.duplicate_of = OrderIntent.State.DUPLICATE, previous
        intent.save()
        _present(intent)
        return intent
    intent.save()
    return _finish(intent)


@retry_database_lock
@transaction.atomic
def confirm(*, customer_id, intent_id, revision, repeat=False, cancel=False):
    require_accepting()
    customer = active_customer(customer_id)
    try:
        intent = OrderIntent.objects.select_for_update().select_related('issue', 'sale', 'customer').get(pk=intent_id, customer=customer)
    except (ValueError, OrderIntent.DoesNotExist):
        raise ValidationError('Заявка не найдена.') from None
    active_customer(customer.pk, revision=intent.customer_revision)
    if intent.sale_id:
        return intent
    if str(intent.revision) != str(revision) or intent.expires_at <= timezone.now():
        raise ValidationError('Расчёт уже изменён или истёк. Откройте актуальное сообщение либо отправьте файл заново.')
    if cancel and intent.state in (OrderIntent.State.PRICES, OrderIntent.State.DUPLICATE):
        intent.state, intent.revision = OrderIntent.State.CANCELLED, intent.revision + 1
        intent.save()
        _present(intent)
        return intent
    if repeat:
        if intent.state != OrderIntent.State.DUPLICATE:
            raise ValidationError('Повторное оформление уже обработано.')
        intent.repeat_allowed = True
        return _finish(intent)
    if intent.state != OrderIntent.State.PRICES:
        raise ValidationError('Заявка больше не ожидает подтверждения цен.')
    return _finish(intent, confirmed=True)
