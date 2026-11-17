"""Корзина и подтверждение. Сетевой расчёт вынесен за пределы транзакции БД."""
from datetime import datetime, timedelta, timezone as tz
from decimal import Decimal, ROUND_FLOOR
import hashlib
import re
import uuid
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from core.db_retry import retry_database_lock
from digital_prices.api import amount, APIError
from digital_prices.models import CatalogState, Product
from digital_prices.provider import wire
from digital_prices.services import effective_rule, selling_price
from digital_prices.customer_terms import new_account_fee
from digital_sales.crypto import encrypt, decrypt
from digital_sales.models import Buyer
from .models import Cart, CartLine, ShopConfig, PurchaseIntent, BalanceHold, PurchaseLine, AuditEvent
from .access import binding
from .catalog import validate, markup
from .public import title


def write_lock():
    # SELECT FOR UPDATE не блокирует строки SQLite. Эта запись берёт write-lock первой.
    ShopConfig.objects.filter(pk=1).update(write_revision=F('write_revision') + 1)


def owned(access, cart_id, revision=None, *, allow_closed=False):
    binding(access)
    cart = Cart.objects.select_for_update().filter(pk=cart_id, chat_id=access.chat_id,
        buyer_id=access.buyer_id).first()
    if not cart or cart.state == 'closed' and not allow_closed:
        raise PermissionDenied('Эта корзина недоступна. Откройте /shop.')
    if revision is not None and str(cart.revision) != str(revision):
        raise ValidationError('Корзина изменилась. Откройте её заново.')
    return cart


@retry_database_lock
@transaction.atomic
def open_cart(access):
    write_lock()
    row = binding(access)
    previous_menu = Cart.objects.filter(chat=row, buyer_id=access.buyer_id, menu_message_id__isnull=False).order_by('-updated_at').values_list('menu_message_id', flat=True).first()
    cart, _ = Cart.objects.get_or_create(chat=row, buyer_id=access.buyer_id,
        state__in=['open', 'credentials', 'quote_pending', 'quoted'],
        defaults={'state': 'open', 'telegram_user_id': access.user_id, 'menu_message_id': previous_menu})
    return cart


def invalidate(cart):
    cart.state, cart.quote_id, cart.quote_expires_at = 'open', '', None
    cart.encrypted_credentials = ''
    cart.credential_groups, cart.price_snapshot = [], {}
    cart.prompt_message_id = None
    cart.revision += 1
    cart.save()


def quantity(product, value):
    limits = product.quantity_limits
    if type(value) is not int or not 1 <= value <= 20:
        raise ValidationError('Количество должно быть от 1 до 20.')
    low, high, step = (limits.get(k) for k in ('min_quantity', 'max_quantity', 'quantity_step'))
    if any(type(v) is not int or v < 1 for v in (low, high, step)) or not low <= value <= high or (value - low) % step:
        raise ValidationError('Количество не соответствует доступному шагу товара.')
    if product.source_type in ('steam_topup', 'steam_gift') and value != 1:
        raise ValidationError('Такую услугу добавляют отдельной строкой по одной единице.')
    stock = product.attributes.get('in_stock')
    if type(stock) is int and value > stock:
        raise ValidationError('Выбранного количества сейчас нет в наличии.')


@retry_database_lock
@transaction.atomic
def add(access, cart_id, revision, product_id, *, mode='', account_key='', parameters=None):
    write_lock()
    cart = owned(access, cart_id, revision)
    if cart.state not in ('open', 'credentials', 'quoted'):
        raise ValidationError('Корзина уже обрабатывается.')
    product = validate(Product.objects.get(pk=product_id), access.buyer_id)
    req, parameters = product.requirements, parameters or {}
    if set(parameters) != set(req.get('parameters', [])):
        raise ValidationError('Укажите параметры товара.')
    if 'amount' in parameters:
        try:
            value = amount(parameters['amount'])
        except APIError:
            raise ValidationError('Укажите положительную сумму с точностью до копейки.') from None
        if value <= 0:
            raise ValidationError('Сумма должна быть больше нуля.')
        parameters = {'amount': str(value)}
    quantity(product, product.quantity_limits.get('min_quantity', 1))
    if req.get('account'):
        modes = req['account_modes']
        # Оба режима требуют явного выбора, старые кнопки его не подменяют.
        if not mode and len(modes) == 1:
            mode = modes[0]
        if mode not in modes:
            raise ValidationError('Выберите новый или существующий аккаунт для этой услуги.')
        if mode == 'new' and product.quantity_limits.get('min_quantity', 1) != 1:
            raise ValidationError('Новый аккаунт оформляется отдельной позицией в одной единице.')
        if account_key:
            raise ValidationError('Для каждой услуги вводятся отдельные реквизиты. Добавьте товар заново.')
        account_key = 'a' + uuid.uuid4().hex[:10]
    elif mode or account_key:
        raise ValidationError('Этому товару группа аккаунта не требуется.')
    if cart.lines.count() >= 30 or cart.lines.aggregate(n=Sum('quantity'))['n'] and cart.lines.aggregate(n=Sum('quantity'))['n'] + product.quantity_limits.get('min_quantity', 1) > 50:
        raise ValidationError('В одной корзине разрешено до 30 строк и 50 единиц.')
    if req.get('account') and not cart.lines.filter(account_key=account_key).exists() and cart.lines.exclude(account_key='').values('account_key').distinct().count() >= 20:
        raise ValidationError('В корзине может быть до 20 аккаунтов.')
    CartLine.objects.create(cart=cart, product=product, quantity=product.quantity_limits.get('min_quantity', 1),
        account_mode=mode, account_key=account_key, parameters=parameters)
    invalidate(cart)
    return cart


@retry_database_lock
@transaction.atomic
def change(access, cart_id, revision, line_id=None, *, delta=0, clear=False, remove=False):
    write_lock()
    cart = owned(access, cart_id, revision)
    if cart.state not in ('open', 'credentials', 'quoted'):
        raise ValidationError('Корзина уже обрабатывается.')
    if clear:
        cart.lines.all().delete()  # Только неподтверждённый состав, не учётные записи.
    else:
        line = cart.lines.select_related('product').get(pk=line_id)
        if remove:
            line.delete()
        else:
            value = line.quantity + delta * line.product.quantity_limits.get('quantity_step', 1)
            quantity(validate(line.product, access.buyer_id), value)
            if sum(cart.lines.values_list('quantity', flat=True)) - line.quantity + value > 50:
                raise ValidationError('В корзине может быть до 50 единиц.')
            line.quantity = value
            line.save(update_fields=['quantity'])
    invalidate(cart)
    return cart


def groups_for(lines):
    groups = {}
    for line in lines:
        req = line.product.requirements
        if line.account_key:
            key = line.account_key
            fields = ([] if line.account_mode == 'new' else ['data'] if req.get('account_format') == 'text'
                      else ['manual_credentials'] if line.product.fulfillment == 'manual' else ['login', 'password'])
            record = {'id': key, 'mode': line.account_mode, 'fields': fields, 'items': []}
            groups.setdefault(key, record)['items'].append(title(line.product.display_name or line.product.source_name))
        if req.get('delivery'):
            key = 'd' + str(line.pk)
            groups[key] = {'id': key, 'line_id': 'l' + str(line.pk), 'fields': req['delivery'], 'items': [title(line.product.source_name)]}
    return list(groups.values())


def validate_accounts(lines):
    """Режим подтверждён каталогом, реквизиты каждой услуги независимы."""
    used = set()
    for line in lines:
        if line.product.requirements.get('account'):
            if (line.account_mode not in line.product.requirements.get('account_modes', [])
                    or not line.account_key or line.account_key in used):
                raise ValidationError('Этот состав использует прежний способ оформления. Соберите корзину заново.')
            if line.account_mode == 'new' and line.quantity != 1:
                raise ValidationError('Каждый новый аккаунт добавляйте отдельной позицией.')
            used.add(line.account_key)


@retry_database_lock
@transaction.atomic
def prepare_credentials(access, cart_id, revision):
    write_lock()
    cart = owned(access, cart_id, revision)
    lines = list(cart.lines.select_related('product').order_by('pk'))
    if not lines:
        raise ValidationError('Корзина пуста.')
    for line in lines:
        quantity(validate(line.product, access.buyer_id), line.quantity)
    validate_accounts(lines)
    cart.credential_groups = groups_for(lines)
    cart.state, cart.revision, cart.encrypted_credentials = 'credentials', cart.revision + 1, ''
    cart.save()
    return cart


def credentials_template(cart):
    text = ['🔐 Ответьте одним сообщением именно на этот запрос. Данные будут видны участникам этой группы.',
            'Для каждой услуги укажите её собственные реквизиты. Они используются только для этой заявки.']
    required = [group for group in cart.credential_groups if group['fields']]
    if len(required) == 1 and required[0]['fields'] in (['manual_credentials'], ['data']):
        return '\n'.join(text + ['', ', '.join(required[0]['items'])[:260],
            'Напишите все сведения в свободной форме одним сообщением.' +
            (' Укажите логин и пароль аккаунта; дополнительные сведения тоже можно включить.'
             if required[0]['fields'] == ['manual_credentials'] else '')])
    text.append('Для нескольких услуг разделите сведения заголовками [1], [2] из списка ниже.')
    for number, group in enumerate(cart.credential_groups, 1):
        if group['fields']:
            text += ['', '[' + str(number) + '] ' + ', '.join(group['items'])[:260]]
            text += (['Все сведения в свободной форме, включая логин и пароль.']
                     if group['fields'] == ['manual_credentials'] else [field + '=' for field in group['fields']])
    return '\n'.join(text)


@sensitive_variables()
def parse_credentials(text, groups):
    if not isinstance(text, str) or len(text.encode('utf-16-le')) // 2 > 3900:
        raise ValidationError('Данные слишком большие. Разделите корзину.')
    expected = {g['id']: g for g in groups if g['fields']}
    aliases = {str(number):g['id'] for number,g in enumerate(groups,1) if g['fields']}
    # У ручной услуги одно свободное сообщение. Для нескольких услуг заголовки
    # отделяют реквизиты; угадывать принадлежность данных разных аккаунтов нельзя.
    free = {key: group for key, group in expected.items() if group['fields'] == ['manual_credentials']}
    if len(expected) == 1 and next(iter(expected.values()))['fields'] in (['manual_credentials'], ['data']):
        key, group = next(iter(expected.items()))
        content = re.sub(r'^\[(?:' + re.escape(key) + '|' + next(k for k,v in aliases.items() if v == key) + r')\][^\n]*\n', '', text, count=1)
        if not content.strip():
            raise ValidationError('Укажите данные для выполнения услуги.')
        if free:
            from .credentials import manual_credentials
            return {key: manual_credentials(content)}
        # Старый шаблон data= также остаётся допустимым.
        return {key: {'data': content[5:] if content.startswith('data=') else content}}
    if free:
        blocks = re.split(r'(?m)^\[([A-Za-z0-9]+)\][^\n]*(?:\n|$)', text)
        if blocks[0].strip() or len(blocks) % 2 != 1:
            raise ValidationError('Разделите сведения заголовками услуг из запроса.')
        manual, remaining = {}, []
        for index in range(1, len(blocks), 2):
            key = aliases.get(blocks[index], blocks[index])
            if key in free:
                if key in manual:
                    raise ValidationError('Повторяется заголовок услуги.')
                from .credentials import manual_credentials
                manual[key] = manual_credentials(blocks[index + 1])
            else:
                remaining.append('[' + key + ']\n' + blocks[index + 1])
        if set(manual) != set(free):
            raise ValidationError('Не хватает данных одной из услуг.')
        return {**manual, **parse_credentials('\n'.join(remaining), [g for g in groups if g['id'] not in free])}
    values, current, current_field = {}, None, None
    optional = {'email_password', 'additional_data'}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.match(r'^\[([A-Za-z0-9]+)\]', line)
        if match:
            current = aliases.get(match[1],match[1])
            if current not in expected or current in values:
                raise ValidationError('Проверьте заголовки групп в шаблоне.')
            values[current] = {}
            current_field = None
            continue
        key, sep, value = line.partition('=')
        if not sep and current_field in ('data', 'additional_data') and current in values:
            values[current][current_field] += '\n' + line
            continue
        key = key.strip()
        allowed = set(expected[current]['fields']) if current in expected else set()
        if allowed == {'login', 'password'}:
            allowed |= optional
        if not sep or current is None or key not in allowed or key in values[current]:
            raise ValidationError('Заполните шаблон без лишних полей и повторов.')
        if not value.strip() or len(value) > (12000 if key in ('data', 'additional_data') else 1024 if key in ('password', 'email_password') else 320):
            raise ValidationError('Не все обязательные поля заполнены корректно.')
        if key == 'friend_link' and not re.fullmatch(r'https://s\.team/p/[A-Za-z0-9-]+/[A-Za-z0-9]+', value):
            raise ValidationError('Проверьте короткую ссылку приглашения Steam.')
        values[current][key] = value
        current_field = key
    if set(values) != set(expected) or any(set(g['fields']) - set(values[g['id']]) for g in expected.values()):
        raise ValidationError('Не хватает данных одной из групп.')
    return values


@retry_database_lock
@transaction.atomic
@sensitive_variables()
def save_credentials(access, cart_id, reply_message_id, text):
    write_lock()
    cart = owned(access, cart_id)
    if cart.state != 'credentials' or cart.prompt_message_id != reply_message_id:
        raise ValidationError('Запрос устарел. Откройте корзину заново.')
    values = parse_credentials(text, cart.credential_groups)
    cart.encrypted_credentials = encrypt(values)
    cart.save(update_fields=['encrypted_credentials'])
    return cart


def allocated(total, weights):
    """Детерминированное распределение копеек; сумма строк строго равна итогу."""
    cents = int(amount(total) * 100)
    weights = [amount(value) for value in weights]
    denominator = sum(weights)
    if not weights or not denominator:
        if not weights:
            raise ValidationError('Не подтверждена стоимость расчёта.')
        return [Decimal(cents // len(weights) + (1 if i < cents % len(weights) else 0)) / 100 for i in range(len(weights))]
    values = [int((Decimal(cents) * w / denominator).to_integral_value(rounding=ROUND_FLOOR)) for w in weights]
    for i in range(cents - sum(values)):
        values[i % len(values)] += 1
    return [Decimal(v) / 100 for v in values]


def make_quote_body(lines):
    accounts = {}
    items = []
    for line in lines:
        item = {'id': 'l' + str(line.pk), 'product_id': line.product.external_id, 'qty': line.quantity}
        if line.account_key:
            accounts[line.account_key] = {'id': line.account_key, 'mode': line.account_mode}
            item['account_id'] = line.account_key
        if line.parameters:
            item['parameters'] = {k: amount(v) for k, v in line.parameters.items()}
        items.append(item)
    return {'game_pricing': 'combined', 'accounts': list(accounts.values()), 'items': items}


def quote_expiration(value, *, now=None):
    """Unix seconds в JSON бывают дробными. Принимаем Decimal без потери микросекунд."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise APIError('invalid_quote')
    seconds = Decimal(value)
    if not seconds.is_finite() or not 0 < seconds < Decimal('253402300799'):
        raise APIError('invalid_quote')
    expires = datetime(1970, 1, 1, tzinfo=tz.utc) + timedelta(microseconds=int(seconds * 1000000))
    now = now or timezone.now()
    if not now < expires <= now + timedelta(minutes=6):
        raise APIError('invalid_quote')
    return expires


def quote_values(response, lines):
    """Проверка обеих котировок: исполнения и базовой клиентской цены."""
    quoted = amount(response.get('total'))
    quote_id, expiry = response.get('quote_id'), response.get('expires_at')
    if (not isinstance(quote_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', quote_id)
            or response.get('currency', '').upper() != 'RUB'):
        raise APIError('invalid_quote')
    expires = quote_expiration(expiry)
    rows = response.get('lines')
    if (not isinstance(rows, list) or len(rows) != len(lines)
            or any(not isinstance(value, dict) for value in rows)):
        raise APIError('invalid_quote')
    costs = {value.get('id'): amount(value.get('price')) for value in rows}
    if set(costs) != {'l' + str(line.pk) for line in lines}:
        raise APIError('invalid_quote')
    try:
        adjustment = Decimal(str(response.get('adjustment', 0)))
        if not adjustment.is_finite() or adjustment != adjustment.quantize(Decimal('.01')):
            raise ValueError
    except (ValueError, ArithmeticError):
        raise APIError('invalid_quote') from None
    if sum(costs.values()) + adjustment != quoted:
        raise APIError('invalid_quote')
    return quote_id, expires, quoted, costs


def quote_cart(access, cart_id, revision, client):
    with transaction.atomic():
        write_lock()
        cart = owned(access, cart_id, revision)
        if cart.state not in ('credentials', 'quoted'):
            raise ValidationError('Сначала заполните данные корзины.')
        lines = list(cart.lines.select_related('product').order_by('pk'))
        for line in lines:
            quantity(validate(line.product, access.buyer_id), line.quantity)
        validate_accounts(lines)
        groups = groups_for(lines)
        if any(g['fields'] for g in groups) and not cart.encrypted_credentials:
            raise ValidationError('Ответьте на общий запрос данных.')
        body = make_quote_body(lines)
        expected_revision = cart.revision
        cart.state = 'quote_pending'
        cart.save(update_fields=['state'])
        settings = [(line.pk, line.product.revision, markup(line.product, access.buyer_id), effective_rule(line.product)) for line in lines]
        account_fee = new_account_fee(Buyer.objects.get(pk=access.buyer_id).name) or Decimal(0)
    try:
        for group in groups:
            if group.get('fields') == ['login']:
                login = decrypt(cart.encrypted_credentials)[group['id']]['login']
                response = client.steam_check(login)
                if response.get('exists') is not True:
                    raise ValidationError('Проверьте логин Steam.')
        has_new = any(line.account_mode == 'new' for line in lines)
        base_costs = {}
        if has_new:
            # Клиентская доплата фиксирована для покупателя. Закупочная доплата
            # /льгота нового аккаунта из adjustment не прибавляется к ней второй раз.
            # Для Xbox new-only базой служит цена строки выбранного API-товара:
            # недопустимый existing для него никогда не отправляется.
            base_lines = [line for line in lines if line.account_mode != 'new'
                          or 'existing' in line.product.requirements.get('account_modes', [])]
            if base_lines:
                base_body = make_quote_body(base_lines)
                for account in base_body['accounts']:
                    account['mode'] = 'existing'
                _, _, base_total, base_prices = quote_values(client.quote(base_body), base_lines)
                base_costs = {line.pk: cost for line, cost in zip(base_lines,
                    allocated(base_total, [base_prices['l' + str(line.pk)] for line in base_lines]), strict=True)}
        quote_id, expires, quoted, costs = quote_values(client.quote(body), lines)
        distributed = allocated(quoted, [costs['l' + str(line.pk)] for line in lines])
        snapshot = {}
        for line, cost, (_, version, fee, rule) in zip(lines, distributed, settings, strict=True):
            # Наценка задана на единицу; округляем подтверждённую цену строки, не сетевую цену × qty.
            base_cost = base_costs.get(line.pk, costs['l' + str(line.pk)]) if has_new else cost
            price = selling_price(base_cost, 'RUB', fee * line.quantity, rule)
            if price is None or price <= 0:
                raise ValidationError('Итоговая цена не определена.')
            surcharge = account_fee if line.account_mode == 'new' else Decimal(0)
            price += surcharge
            snapshot[str(line.pk)] = {'cost': str(cost), 'price': str(price), 'markup': str(fee),
                'product_revision': version, 'rule': rule, 'quantity': line.quantity,
                'name': title(line.product.display_name or line.product.source_name),
                'product_id': line.product.external_id, 'kind': line.product.source_type,
                'account_mode': line.account_mode, 'new_account_fee': str(surcharge)}
        with transaction.atomic():
            write_lock()
            current = owned(access, cart_id, expected_revision)
            if (new_account_fee(Buyer.objects.get(pk=access.buyer_id).name) or Decimal(0)) != account_fee:
                raise ValidationError('Условия оформления обновились. Повторите расчёт.')
            # Изменение индивидуальных цен во время запроса требует нового расчёта.
            for line, (_, version, fee, rule) in zip(lines, settings, strict=True):
                product = Product.objects.get(pk=line.product_id)
                if product.revision != version or markup(product, access.buyer_id) != fee:
                    raise ValidationError('Цены обновились. Повторите расчёт.')
            current.quote_id, current.quote_expires_at = quote_id, expires
            current.quoted_total, current.client_total = quoted, sum(Decimal(v['price']) for v in snapshot.values())
            current.price_snapshot, current.credential_groups = snapshot, groups
            current.catalog_revision = CatalogState.objects.get(pk=1).revision
            current.quote_body = {'accounts': body['accounts']}
            current.state, current.quote_revision = 'quoted', current.revision
            current.save()
            return current
    except Exception:
        with transaction.atomic():
            current = Cart.objects.get(pk=cart_id)
            if current.revision == expected_revision and current.state == 'quote_pending':
                current.state = 'credentials'
                current.save(update_fields=['state'])
        raise


def available_balance(buyer):
    held = BalanceHold.objects.filter(buyer=buyer, state='active').aggregate(v=Sum('remaining'))['v'] or Decimal(0)
    return buyer.balance - held


@retry_database_lock
@transaction.atomic
@sensitive_variables()
def confirm(access, cart_id, revision):
    write_lock()
    cart = owned(access, cart_id, revision, allow_closed=True)
    existing = PurchaseIntent.objects.filter(cart=cart).first()
    if existing:
        return existing
    config = ShopConfig.objects.get(pk=1)
    if not config.purchases_enabled or not config.supplier_id or not config.actor_id:
        raise ValidationError('Автоматическое оформление пока выключено. Обратитесь к администратору.')
    from digital_sales.services import require
    require(config.actor, 'digital_sales.create_digital_sales', 'sales.create_sale',
            'digital_sales.complete_digital_sales', 'sales.mark_sale_paid')
    if (cart.state != 'quoted' or cart.quote_revision != cart.revision or not cart.quote_expires_at or
            cart.quote_expires_at <= timezone.now() + timedelta(seconds=10)):
        raise ValidationError('Расчёт устарел. Обновите цену и подтвердите её заново.')
    if cart.catalog_revision != CatalogState.objects.get(pk=1).revision:
        raise ValidationError('Каталог обновился. Нужен новый расчёт.')
    lines = list(cart.lines.select_related('product'))
    validate_accounts(lines)
    account_fee = new_account_fee(Buyer.objects.get(pk=access.buyer_id).name) or Decimal(0)
    for line in lines:
        validate(line.product, access.buyer_id)
        stored = cart.price_snapshot.get(str(line.pk), {})
        if stored.get('product_revision') != line.product.revision or stored.get('markup') != str(markup(line.product, access.buyer_id)):
            raise ValidationError('Цена товара изменилась. Нужен новый расчёт.')
        if (stored.get('account_mode', 'existing' if line.account_key else '') != line.account_mode
                or Decimal(stored.get('new_account_fee', '0')) != (account_fee if line.account_mode == 'new' else Decimal(0))):
            raise ValidationError('Условия оформления изменились. Нужен новый расчёт.')
    buyer = Buyer.objects.select_for_update().get(pk=access.buyer_id)
    if cart.client_total is None or cart.client_total <= 0:
        raise ValidationError('Итоговая сумма корзины должна быть больше нуля. Обновите расчёт.')
    # Покупателю разрешён долг. Hold учитывает обязательство по заказу,
    # а списание после выполнения может сделать баланс отрицательным.
    identifier = 'gb-' + uuid.uuid4().hex
    data = decrypt(cart.encrypted_credentials) if cart.encrypted_credentials else {}
    accounts, deliveries = [], []
    for group in cart.credential_groups:
        if 'line_id' in group:
            deliveries.append({'id': group['line_id'], **data[group['id']]})
        elif group.get('mode') == 'existing':
            values = data[group['id']]
            accounts.append({'id': group['id'], **({'data': values['data']} if group['fields'] == ['data'] else {'credentials': values})})
    body = {'client_order_id': identifier, 'quote_id': cart.quote_id, 'accounts': accounts, 'deliveries': deliveries}
    serialized = wire(body)
    intent = PurchaseIntent.objects.create(cart=cart, client_order_id=identifier,
        encrypted_body=encrypt({'wire': serialized}), body_hash=hashlib.sha256(serialized.encode()).hexdigest(), next_at=timezone.now())
    BalanceHold.objects.create(intent=intent, buyer=buyer, amount=cart.client_total, remaining=cart.client_total)
    for line in cart.lines.order_by('pk'):
        snapshot = cart.price_snapshot[str(line.pk)]
        PurchaseLine.objects.create(intent=intent, cart_line=line, line_id='l' + str(line.pk), cost=Decimal(snapshot['cost']),
            client_price=Decimal(snapshot['price']), snapshot=snapshot)
    cart.state, cart.encrypted_credentials = 'closed', ''
    cart.save(update_fields=['state', 'encrypted_credentials'])
    AuditEvent.objects.create(kind='purchase_reserved', intent=intent, detail={
        'buyer': buyer.pk, 'lines': cart.lines.count(), 'telegram_user_id': access.user_id, 'chat_id': access.chat_id})
    return intent
