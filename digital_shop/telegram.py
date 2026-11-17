"""Общий магазин группы; callback проверяет участника, покупателя и ревизию корзины."""
import re
import base64
import uuid
from contextvars import ContextVar
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from digital_prices.api import APIError, parse_page
from digital_prices.models import Product, Integration
from digital_prices.provider import ProviderClient
from digital_prices.customer_terms import new_account_fee
from digital_sales.crypto import encrypt, decrypt
from digital_sales.models import BuyerBalanceChat, Buyer, DigitalBot
from telegram_bots.client import TelegramError
from .access import member, binding
from .catalog import products, caption, validate, code_family, KINDS
from digital_prices.classification import COUNTRIES, region_code
from .models import ChatEvent, Cart, PurchaseIntent, ShopChat, AuditEvent
from .public import checked, title
from . import services

PREFIX = 's:'
RENEW = ContextVar('shop_renew', default=lambda: None)


def ingest(update):
    """Вызывается в транзакции offset; сохраняются только команды магазина и ответы на его запрос."""
    callback = update.get('callback_query')
    source = callback.get('message') if isinstance(callback, dict) else update.get('message')
    if not isinstance(source, dict):
        return False
    chat = source.get('chat') or {}
    if not isinstance(chat, dict) or chat.get('type') not in ('group', 'supergroup'):
        return False
    text = source.get('text') or ''
    is_command = isinstance(text, str) and re.match(r'^/shop(?:@[\w]+)?(?:\s|$)', text)
    if is_command and '@' in text.split()[0] and text.split()[0].split('@', 1)[1].casefold() != DigitalBot.objects.get(pk=1).username.casefold():
        return False
    is_callback = isinstance(callback, dict) and str(callback.get('data', '')).startswith(PREFIX)
    reply = source.get('reply_to_message') or {}
    is_reply = (isinstance(reply, dict) and Cart.objects.filter(chat_id=chat.get('id'),
        prompt_message_id=reply.get('message_id'), state__in=['open', 'credentials']).exists()) if reply.get('message_id') else False
    migration = bool(source.get('migrate_to_chat_id') or source.get('migrate_from_chat_id'))
    if not (is_command or is_callback or is_reply or migration):
        return False
    ChatEvent.objects.get_or_create(update_id=update['update_id'], defaults={'encrypted_payload': encrypt(update)})
    return True


def button(cart, text, action, arg=''):
    # Telegram разрешает всего 64 байта callback_data. Компактный UUID оставляет
    # место идентификатору выбранной группы аккаунта без серверных URL/секретов.
    compact = base64.urlsafe_b64encode(cart.pk.bytes).decode('ascii').rstrip('=')
    value = f'{PREFIX}{compact}:{cart.revision}:{action}:{arg}'
    if len(value.encode()) > 64:
        raise ValidationError('Слишком длинный идентификатор кнопки.')
    return {'text': text[:60], 'callback_data': value}


def show(client, cart, text, rows, *, new_message=False):
    from .access import Access
    binding(Access(cart.chat_id, cart.buyer_id, cart.telegram_user_id))
    data = {'chat_id': cart.chat_id, 'text': checked(text), 'reply_markup': {'inline_keyboard': rows}}
    previous_id = cart.menu_message_id
    if previous_id and not new_message:
        try:
            result = client.call('editMessageText', {**data, 'message_id': cart.menu_message_id})
        except TelegramError as exc:
            if exc.category != 'message_missing':
                raise
            result = client.call('sendMessage', data)
    else:
        result = client.call('sendMessage', data)
    if not isinstance(result, dict) or type(result.get('message_id')) is not int:
        raise TelegramError('invalid_response', uncertain=True)
    cart.menu_message_id = result['message_id']
    cart.save(update_fields=['menu_message_id'])
    if new_message and previous_id and previous_id != cart.menu_message_id:
        try:
            # Старое меню остаётся в истории, но больше не уводит пользователя
            # к кнопкам выше. Убираем клавиатуру только после успешной новой отправки.
            client.call('editMessageReplyMarkup', {'chat_id': cart.chat_id, 'message_id': previous_id,
                                                  'reply_markup': {'inline_keyboard': []}})
        except TelegramError:
            pass  # Старое сообщение могло быть удалено; новое меню уже доступно.


def home(client, cart, *, new_message=False):
    kinds = {p.source_type for p in products(cart.buyer_id)}
    rows = [[button(cart, KINDS[k], 'kc' if k == 'code' else 'k', '' if k == 'code' else k + '.0')] for k in KINDS if k in kinds]
    rows += [[button(cart, '🔎 Поиск игр', 'sp')], [button(cart, '🛒 Корзина', 'c'), button(cart, '💰 Баланс', 'b')],
             [button(cart, '📦 Мои заказы', 'o')]]
    show(client, cart, '🛍 Цифровой магазин GameBAT\n' + title(cart.buyer.name) +
         '\nКорзина и баланс общие для этой группы. Заказ может продолжить любой участник.', rows, new_message=new_message)


def listing(client, cart, kind, page):
    match = re.fullmatch(r'code(\d{1,2})r(\d{1,2})', kind)
    rows = products(cart.buyer_id, kind='code' if match else kind if kind != 'search' else None)
    if match:
        families = sorted({code_family(p) for p in rows})
        family = families[int(match[1])]
        rows = [p for p in rows if code_family(p) == family]
        regions = sorted({p.region for p in rows})
        rows = [p for p in rows if p.region == regions[int(match[2])]]
    if kind == 'search':
        rows = [p for p in rows if p.pk in cart.search_product_ids]
    start = max(0, page) * 8
    visible = rows[start:start + 8]
    keys = [[button(cart, caption(p, cart.buyer_id), 'p', str(p.pk))] for p in visible]
    navigation = []
    if page > 0:
        navigation.append(button(cart, '←', 'k', f'{kind}.{page-1}'))
    if start + 8 < len(rows):
        navigation.append(button(cart, '→', 'k', f'{kind}.{page+1}'))
    if navigation:
        keys.append(navigation)
    keys += [[button(cart, '🛒 Корзина', 'c'), button(cart, 'В меню', 'h')]]
    show(client, cart, ('🔎 Результаты поиска' if kind == 'search' else KINDS.get(kind, 'Каталог')) +
         (f'\nСтраница {page+1}. Выберите товар.' if visible else '\nДоступных предложений с ценой пока нет.'), keys)


def product_card(client, cart, pk):
    product = validate(Product.objects.get(pk=pk), cart.buyer_id)
    text = caption(product, cart.buyer_id)
    editions = []
    if product.source_type in ('game', 'xbox_game', 'steam_gift'):
        api = provider_client()
        try:
            detail = api.product(product.external_id)
            if detail.get('product_id') != product.external_id:
                raise APIError('product_identity_conflict')
            offers, _ = parse_page({'items': detail.get('editions', [])[:50], 'page': 1, 'has_more': False}, 1)
            ids = {row.identity for row in offers}
            editions = [p for p in products(cart.buyer_id) if p.external_id in ids and p.pk != product.pk]
            # Изображения, описания и ссылки поставщика не пересылаются.
        finally:
            api.close()
    rows = [[button(cart, 'Добавить в корзину', 'a', str(pk))]]
    rows += [[button(cart, 'Издание: ' + caption(p, cart.buyer_id), 'p', str(p.pk))] for p in editions[:8]]
    rows.append([button(cart, '🛒 Корзина', 'c'), button(cart, 'В меню', 'h')])
    show(client, cart, text + '\nОкончательная цена будет рассчитана перед подтверждением.', rows)


def cart_view(client, cart):
    text, rows = ['🛒 Ваша корзина'], []
    for i, line in enumerate(cart.lines.select_related('product').order_by('pk'), 1):
        text.append(f'{i}. {caption(line.product, cart.buyer_id, mode=getattr(line, "account_mode", ""))} × {line.quantity}')
        if line.parameters:
            text.append('Сумма пополнения: ' + str(line.parameters.get('amount', '')))
        rows.append([button(cart, f'Удалить позицию {i}', 'x', str(line.pk))])
    if rows:
        rows += [[button(cart, 'Рассчитать и оформить', 'q')]]
    else:
        text.append('Корзина пуста.')
    rows += [[button(cart, 'В меню', 'h')]]
    show(client, cart, '\n'.join(text), rows)


def request_input(client, cart, kind, text, **fields):
    for name, value in fields.items():
        setattr(cart, name, value)
    cart.input_kind = kind
    data = {'chat_id': cart.chat_id, 'text': checked(text), 'reply_markup': {'force_reply': True, 'selective': False}}
    result = client.call('sendMessage', data)
    if not isinstance(result, dict) or type(result.get('message_id')) is not int:
        raise TelegramError('invalid_response', uncertain=True)
    cart.prompt_message_id = result['message_id']
    cart.save()


def provider_client():
    from integrations.crypto import decrypt_secret
    config = Integration.objects.filter(pk=1, enabled=True).first()
    if config is None or not config.encrypted_key:
        raise ValidationError('Расчёт временно недоступен. Обратитесь к администратору.')
    return ProviderClient(decrypt_secret(config.encrypted_key), heartbeat=RENEW.get())


def calculated(client, access, cart):
    api = provider_client()
    try:
        cart = services.quote_cart(access, cart.pk, cart.revision, api)
    finally:
        api.close()
    text = ['🧾 Окончательный расчёт GameBAT']
    for i, row in enumerate(cart.price_snapshot.values(), 1):
        text.append(f'{i}. {row["name"]} × {row["quantity"]}: {row["price"]} ₽')
        if row.get('account_mode') == 'new':
            text.append(f'🆕 Новый аккаунт · доплата {row["new_account_fee"]} ₽ уже включена.')
        elif row.get('account_mode') == 'existing':
            text.append('🔐 На существующий аккаунт.')
    text += [f'Итого: {cart.client_total:.2f} ₽', 'Расчёт действует до ' + timezone.localtime(cart.quote_expires_at).strftime('%H:%M:%S'),
             'Нажатие «Подтвердить» запускает оформление. Сумма спишется после выполнения; баланс может стать отрицательным.']
    show(client, cart, '\n'.join(text), [[button(cart, '✅ Подтвердить', 'ok')],
        [button(cart, 'Обновить расчёт', 'rq'), button(cart, 'Изменить корзину', 'c')]])


def add_product(client, access, cart, arg, *, parameters=None):
    parts = arg.split('.')
    if not parts[0].isdecimal() or len(parts) > 3:
        raise ValidationError('Кнопка устарела.')
    product = validate(Product.objects.get(pk=int(parts[0])), cart.buyer_id)
    mode, account = parts[1] if len(parts) > 1 else '', parts[2] if len(parts) > 2 else ''
    if product.requirements.get('account') and not mode and len(product.requirements['account_modes']) > 1:
        fee = new_account_fee(Buyer.objects.get(pk=cart.buyer_id).name) or 0
        show(client, cart, caption(product, cart.buyer_id) + '\nНа какой аккаунт оформить услугу?',
             [[button(cart, f'🆕 Новый аккаунт (+{fee} ₽)', 'a', str(product.pk) + '.new')],
              [button(cart, '🔐 Существующий — ввести данные', 'a', str(product.pk) + '.existing')],
              [button(cart, 'К товару', 'p', str(product.pk))]])
        return
    if product.requirements.get('parameters') and parameters is None:
        request_input(client, cart, 'amount', 'Укажите сумму пополнения одним числом в валюте выбранного кошелька.',
            input_product=product, input_mode=mode, input_account=account)
        return
    cart = services.add(access, cart.pk, cart.revision, product.pk, mode=mode, account_key=account, parameters=parameters)
    if product.requirements.get('account'):
        # Никакой адресной книги: после выбора existing сразу запрашиваются
        # новые данные текущих услуг, а new не требует реквизитов покупателя.
        cart = services.prepare_credentials(access, cart.pk, cart.revision)
        if any(group['fields'] for group in cart.credential_groups):
            request_input(client, cart, 'credentials', services.credentials_template(cart))
        else:
            calculated(client, access, cart)
    else:
        cart_view(client, cart)


def respond(client, source, access):
    reply_id = source.get('reply_to_message', {}).get('message_id')
    cart = Cart.objects.filter(chat_id=access.chat_id, buyer_id=access.buyer_id,
        prompt_message_id=reply_id, state__in=['open', 'credentials']).first()
    if cart is None:
        raise PermissionDenied('Этот запрос уже устарел. Откройте корзину в меню группы.')
    text = source.get('text')
    if cart.input_kind == 'credentials':
        cart = services.save_credentials(access, cart.pk, reply_id, text)
        # Удаление — только после сохранения зашифрованного значения; не обещаем скрыть его от участников.
        if BuyerBalanceChat.objects.filter(pk=access.chat_id, can_delete=True).exists():
            try:
                client.call('deleteMessage', {'chat_id': access.chat_id, 'message_id': source['message_id']})
            except TelegramError:
                pass
        calculated(client, access, cart)
    elif cart.input_kind == 'amount':
        if not isinstance(text, str):
            raise ValidationError('Нужна сумма текстом.')
        add_product(client, access, cart, f'{cart.input_product_id}.{cart.input_mode}.{cart.input_account}',
            parameters={'amount': text.strip().replace(',', '.')})
    elif cart.input_kind == 'search':
        if not isinstance(text, str) or not 2 <= len(text.strip()) <= 150:
            raise ValidationError('Введите название длиной от 2 до 150 символов.')
        api = provider_client()
        try:
            response = api.search(text.strip(), platform=cart.search_platform, region=cart.search_region or None)
            offers, _ = parse_page({'page': 1, 'has_more': False, 'items': response.get('items')}, 1)
            known = set(Product.objects.filter(external_id__in=[o.identity for o in offers], api_version=2).values_list('external_id', flat=True))
            if any(o.identity not in known for o in offers):
                from digital_sales.notifications import enqueue_alert
                enqueue_alert('shop_discovery:' + str(cart.pk), 'В магазине найдены новые варианты игр. Нужны проверка карточек и назначение цены в CRM.')
            cart.search_query = text.strip()
            cart.search_product_ids = list(Product.objects.filter(external_id__in=known).values_list('pk', flat=True))
            cart.save(update_fields=['search_query', 'search_product_ids'])
        finally:
            api.close()
        listing(client, cart, 'search', 0)


def migrate_chat(source, client):
    """Переносится только подтверждённая Telegram миграция той же группы."""
    old = source.get('chat', {}).get('id') if source.get('migrate_to_chat_id') else source.get('migrate_from_chat_id')
    new = source.get('migrate_to_chat_id') or source.get('chat', {}).get('id')
    if type(old) is not int or type(new) is not int or old >= 0 or new >= 0:
        return
    metadata = client.call('getChat', {'chat_id': new})
    me = client.call('getMe')
    rights = client.call('getChatMember', {'chat_id': new, 'user_id': me.get('id')})
    verified = (isinstance(metadata, dict) and metadata.get('id') == new and metadata.get('type') == 'supergroup'
                and isinstance(rights, dict) and rights.get('status') in ('administrator', 'creator'))
    with transaction.atomic():
        services.write_lock()
        row = ShopChat.objects.select_for_update().filter(binding_id=old).first()
        if row:
            was_enabled = row.enabled
            row.enabled = False
            row.save(update_fields=['enabled'])
            previous = BuyerBalanceChat.objects.select_for_update().get(pk=old)
            target = BuyerBalanceChat.objects.select_for_update().filter(pk=new).first()
            if verified and previous.buyer_id and (target is None or target.buyer_id in (None, previous.buyer_id)):
                if not Cart.objects.filter(chat_id=new).exclude(state='closed').exists():
                    buyer_id = previous.buyer_id
                    previous.buyer = None
                    previous.save(update_fields=['buyer'])
                    target, _ = BuyerBalanceChat.objects.get_or_create(pk=new, defaults={'title': str(metadata.get('title', ''))[:255]})
                    target.buyer_id = buyer_id
                    target.can_pin, target.can_delete = rights.get('can_pin_messages') is True, rights.get('can_delete_messages') is True
                    target.save(update_fields=['buyer', 'can_pin', 'can_delete', 'updated_at'])
                    replacement, _ = ShopChat.objects.get_or_create(binding=target)
                    replacement.enabled = was_enabled
                    replacement.save(update_fields=['enabled'])
                    for cart in Cart.objects.filter(chat_id=old, buyer_id=buyer_id):
                        cart.chat, cart.menu_message_id, cart.prompt_message_id = target, None, None
                        if cart.state != 'closed':
                            services.invalidate(cart)
                        else:
                            cart.revision += 1
                            cart.save(update_fields=['chat', 'menu_message_id', 'prompt_message_id', 'revision'])
                    from .models import ResultDelivery
                    for delivery in ResultDelivery.objects.filter(chat_id=old, buyer_id=buyer_id, state='queued'):
                        delivery.chat_id = new
                        delivery.save(update_fields=['chat_id'])
                    from digital_sales.models import BalanceChatPublication
                    for notice in BalanceChatPublication.objects.filter(chat_id=old, buyer_id=buyer_id, state='queued'):
                        notice.chat = target
                        notice.save(update_fields=['chat'])
                    AuditEvent.objects.create(kind='chat_migrated', detail={'old': old, 'new': new, 'buyer': buyer_id})
                    return
            AuditEvent.objects.create(kind='chat_migration_review', detail={'old': old, 'new': new})
            from digital_sales.notifications import enqueue_alert
            enqueue_alert(f'shop_migration:{old}:{new}',
                'Telegram изменил идентификатор группы цифрового магазина. Магазин приостановлен; проверьте привязку и права в CRM.')


def handle(client, update):
    callback = update.get('callback_query')
    source = callback.get('message') if isinstance(callback, dict) else update.get('message')
    if not isinstance(source, dict):
        return
    if source.get('migrate_to_chat_id') or source.get('migrate_from_chat_id'):
        migrate_chat(source, client)
        return
    sender = callback.get('from') if isinstance(callback, dict) else source.get('from')
    access = member(client, chat=source.get('chat'), sender=sender, sender_chat=None if callback else source.get('sender_chat'))
    if callback:
        match = re.fullmatch(r's:([A-Za-z0-9_-]{22}|[0-9a-f]{32}):(\d{1,10}):([A-Za-z+\-]{1,2}):(.*)', str(callback.get('data', '')))
        if not match:
            raise ValidationError('Кнопка устарела.')
        cart_id = uuid.UUID(bytes=base64.urlsafe_b64decode(match[1] + '==')) if len(match[1]) == 22 else uuid.UUID(hex=match[1])
        action, arg = match[3], match[4]
        try:
            client.call('answerCallbackQuery', {'callback_query_id': callback['id']})
        except TelegramError:
            # Просроченный индикатор нажатия не должен прерывать действие:
            # результат или ошибка выводятся обычным сообщением в исходную группу.
            pass
        cart = services.owned(access, cart_id, allow_closed=True)
        confirmed = action == 'ok' and PurchaseIntent.objects.filter(cart=cart).exists()
        if str(cart.revision) != match[2] or cart.state == 'closed' and not confirmed:
            # Другой участник мог уже изменить общую корзину. Показываем её
            # актуальный состав, не выполняя устаревшее изменение/подтверждение.
            shared = services.open_cart(access)
            if source.get('message_id') != shared.menu_message_id:
                home(client, shared, new_message=True)
                try:
                    client.call('editMessageReplyMarkup', {'chat_id': access.chat_id,
                        'message_id': source['message_id'], 'reply_markup': {'inline_keyboard': []}})
                except TelegramError:
                    pass
            else:
                cart_view(client, shared)
            return
        if action == 'h':
            home(client, cart)
        elif action == 'k':
            kind, _, page = arg.rpartition('.')
            if (kind not in (*KINDS, 'search') and not re.fullmatch(r'code\d{1,2}r\d{1,2}', kind)) or not page.isdecimal():
                raise ValidationError('Категория не найдена.')
            listing(client, cart, kind, int(page))
        elif action == 'p':
            product_card(client, cart, int(arg))
        elif action == 'am':
            # Старые кнопки больше не ведут на удалённый экран выбора аккаунта.
            pk, _, _ = arg.partition('.')
            product_card(client, cart, int(pk))
        elif action == 'a':
            add_product(client, access, cart, arg)
        elif action == 'c':
            cart_view(client, cart)
        elif action == 'x':
            cart = services.change(access, cart.pk, cart.revision, int(arg), remove=True)
            cart_view(client, cart)
        elif action in ('+', '-', 'cl'):
            cart_view(client, cart)  # Старые кнопки больше не меняют количество и не очищают общий заказ.
        elif action == 'q':
            cart = services.prepare_credentials(access, cart.pk, cart.revision)
            if any(g['fields'] for g in cart.credential_groups):
                request_input(client, cart, 'credentials', services.credentials_template(cart))
            else:
                calculated(client, access, cart)
        elif action == 'rq':
            calculated(client, access, cart)
        elif action == 'ok':
            intent = services.confirm(access, cart.pk, cart.revision)
            text = (f'Этот расчёт заказа {intent.pk.hex[:8]} уже закрыт без оформления. Откройте /shop для нового расчёта.'
                    if intent.state == 'failed' else f'✅ Заказ GameBAT {intent.pk.hex[:8]} принят в обработку. Результат появится в этой группе.')
            client.message(access.chat_id, checked(text))
            home(client, services.open_cart(access))
        elif action == 'b':
            buyer = Buyer.objects.get(pk=access.buyer_id)
            show(client, cart, f'💰 Общий баланс: {buyer.balance:.2f} ₽\nС учётом заказов в обработке: {services.available_balance(buyer):.2f} ₽\nОформление с отрицательным балансом разрешено.',
                 [[button(cart, 'В меню', 'h')]])
        elif action == 'o':
            orders = PurchaseIntent.objects.filter(cart__buyer_id=access.buyer_id,
                cart__chat_id=access.chat_id).order_by('-created_at')[:10]
            names = {'done': 'Выполнен', 'failed': 'Не оформлен', 'review': 'Проверяется сотрудником',
                     'queued': 'Ожидает оформления', 'uncertain': 'Уточняется', 'processing': 'Выполняется', 'submitting': 'Оформляется'}
            text = ['📦 Заказы этой группы'] + [f'{o.pk.hex[:8]} · {names.get(o.state, "Уточняется")} · {o.cart.client_total:.2f} ₽' for o in orders]
            show(client, cart, '\n'.join(text), [[button(cart, 'В меню', 'h')]])
        elif action == 'sp':
            show(client, cart, 'Выберите платформу для поиска игры.',
                [[button(cart, label, 'sq', platform)] for platform, label in [('playstation', 'PlayStation'), ('xbox', 'Xbox'), ('steam', 'Steam')]])
        elif action == 'sq' and arg in ('playstation', 'xbox', 'steam'):
            if arg == 'playstation':
                show(client, cart, 'Выберите регион PlayStation.', [[button(cart, COUNTRIES[region_code(region)], 'sr', region)]
                    for region in ('turkey', 'sng', 'india', 'poland', 'indonesia', 'usa')])
            else:
                request_input(client, cart, 'search', 'Ответьте названием игры на это сообщение.', search_platform=arg,
                    search_region='usa' if arg == 'xbox' else '')
        elif action == 'sr' and arg in ('turkey', 'sng', 'india', 'poland', 'indonesia', 'usa'):
            request_input(client, cart, 'search', 'Ответьте названием игры на это сообщение.', search_platform='playstation', search_region=arg)
        elif action == 'kc':
            families = sorted({code_family(p) for p in products(cart.buyer_id, kind='code')})
            show(client, cart, 'Цифровые коды · выберите платформу',
                [[button(cart, family, 'kr', str(i))] for i, family in enumerate(families[:99])] + [[button(cart, 'В меню', 'h')]])
        elif action == 'kr' and arg.isdecimal():
            rows = products(cart.buyer_id, kind='code')
            families = sorted({code_family(p) for p in rows})
            family = families[int(arg)]
            regions = sorted({p.region for p in rows if code_family(p) == family})
            show(client, cart, family + ' · выберите регион',
                [[button(cart, COUNTRIES.get(region_code(region), title(region)), 'k', f'code{arg}r{i}.0')]
                 for i, region in enumerate(regions[:99])] + [[button(cart, 'К платформам', 'kc')]])
    elif str(source.get('text', '')).startswith('/shop'):
        home(client, services.open_cart(access), new_message=True)
    else:
        respond(client, source, access)


def process_one(client, *, renew=lambda: None):
    event = ChatEvent.objects.filter(state='queued').order_by('update_id').first()
    if event is None:
        return False
    with transaction.atomic():
        stored = ChatEvent.objects.select_for_update().get(pk=event.pk)
        if stored.state != 'queued':
            return False
        stored.state = 'processing'
        stored.save(update_fields=['state'])
    update = decrypt(event.encrypted_payload)
    token = RENEW.set(renew)
    try:
        handle(client, update)
    except (ValidationError, PermissionDenied, APIError, Product.DoesNotExist, Cart.DoesNotExist, ValueError, IndexError) as exc:
        callback = update.get('callback_query') or {}
        source = callback.get('message') or update.get('message') or {}
        # Ни exception API, ни введённые реквизиты не отображаются пользователю.
        text = 'Не удалось выполнить действие. Откройте /shop заново или обратитесь к @GameBAT_Store.'
        if isinstance(exc, (ValidationError, PermissionDenied)):
            candidate = ' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            try:
                text = checked(candidate)
            except ValidationError:
                pass
        if isinstance(exc, APIError):
            text = {'rate_limited':'Сервис временно ограничил запросы. Попробуйте рассчитать корзину чуть позже.',
                'network_timeout':'Расчёт не получен вовремя. Повторите попытку в корзине; покупка не запускалась.',
                'invalid_quote':'Не удалось проверить расчёт. Повторите попытку в корзине; покупка не запускалась.'}.get(exc.category,text)
        action = str(callback.get('data','')).split(':')[3:4]
        AuditEvent.objects.create(kind='chat_action_rejected',detail={'update_id':event.pk,
            'action':action[0] if action else 'message',
            'category':exc.category if isinstance(exc,APIError) else 'permission' if isinstance(exc,PermissionDenied) else 'validation'})
        try:
            if callback.get('id'):
                client.call('answerCallbackQuery', {'callback_query_id': callback['id'], 'text': text[:180], 'show_alert': True})
        except TelegramError:
            pass
        try:
            # Toast callback может уже истечь после сетевого расчёта. Ошибка
            # обязательно остаётся видимым сообщением, без исходного ответа API.
            if BuyerBalanceChat.objects.filter(pk=source.get('chat', {}).get('id'), buyer__isnull=False).exists():
                client.message(source['chat']['id'], checked(text))
        except TelegramError:
            pass
        event.state = 'rejected'
    except TelegramError:
        # Повтор небезопасной отправки не выполняется автоматически.
        event.state = 'uncertain'
    else:
        event.state = 'done'
    finally:
        RENEW.reset(token)
    event.encrypted_payload = ''
    event.save(update_fields=['state', 'encrypted_payload'])
    return True
