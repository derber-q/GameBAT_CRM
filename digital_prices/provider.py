"""Единственный транспорт v2. Ответы и адрес поставщика не предназначены покупателю."""
from datetime import timedelta
from decimal import Decimal
import json
import hashlib
import re
import time
from urllib.parse import quote
import requests
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from core.db_retry import retry_database_lock
from core.external_policy import require_live_operation
from .api import APIError
from .models import ProviderGate

ROOT = 'https://yanstore.ru/api/external/v2/'
ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')
BUSINESS_ERRORS = frozenset(('category_not_available product_unavailable account_required account_mode_mismatch '
    'account_data_required insufficient_balance price_changed quote_expired quote_already_used idempotency_conflict '
    'order_not_editable not_found delivery_data_required invalid_parameters bad_login steam_user_not_found '
    'bad_friend_link bad_qty bad_amount out_of_stock temporarily_unavailable').split())


def wire(value):
    """Канонический JSON с настоящими десятичными числами, без перехода через float."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise APIError('invalid_amount')
        return format(value, 'f')
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k) + ':' + wire(value[k]) for k in sorted(value)) + '}'
    if isinstance(value, list):
        return '[' + ','.join(wire(v) for v in value) + ']'
    if value is None or type(value) in (str, bool, int):
        return json.dumps(value, ensure_ascii=False)
    raise APIError('invalid_payload')


@retry_database_lock
@transaction.atomic
def slot(priority):
    ProviderGate.objects.get_or_create(pk=1)
    # Сначала запись: SQLite сериализует конкурирующие процессы до чтения окна.
    from django.db.models import F
    ProviderGate.objects.filter(pk=1).update(revision=F('revision') + 1)
    gate = ProviderGate.objects.select_for_update().get(pk=1)
    now = timezone.now()
    tick = int(now.timestamp() * 1000)
    recent = [n for n in gate.requests_at if type(n) is int and n > tick - 61000]
    delay = 0
    if gate.blocked_until and gate.blocked_until > now:
        delay = max(1, int((gate.blocked_until - now).total_seconds()) + 1)
    if priority == 'urgent':
        gate.urgent_until = now + timedelta(seconds=5)
    elif gate.urgent_until and gate.urgent_until > now:
        delay = max(delay, 1)
    if len(recent) >= 20:
        delay = max(delay, (recent[0] + 61000 - tick) // 1000 + 1)
    if not delay:
        recent.append(tick)
    gate.requests_at = recent
    gate.save(update_fields=['requests_at', 'urgent_until'])
    return delay


@retry_database_lock
@transaction.atomic
def block(seconds):
    gate, _ = ProviderGate.objects.get_or_create(pk=1)
    until = timezone.now() + timedelta(seconds=seconds)
    if not gate.blocked_until or gate.blocked_until < until:
        gate.blocked_until = until
        gate.save(update_fields=['blocked_until'])


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise APIError('invalid_identifier')
    return quote(value, safe='')


class ProviderClient:
    def __init__(self, key, *, session=None, priority='urgent', heartbeat=lambda: None, sleeper=time.sleep):
        require_live_operation('digital_prices_api')
        self.key, self.session = key, session or requests.Session()
        self.priority, self.heartbeat, self.sleep = priority, heartbeat, sleeper

    @sensitive_variables()
    def request(self, method, path, *, params=None, body=None, serialized=None):
        require_live_operation('digital_prices_api')
        # Адреса составляются только методами ниже; пользовательский URL сюда не принимается.
        if not re.fullmatch(r'(?:balance|products(?:/search|/[A-Za-z0-9_.%:-]+)?|steam-check|quotes|orders(?:/[A-Za-z0-9_.%:-]+(?:/accounts/[A-Za-z0-9_.%:-]+)?)?)', path):
            raise APIError('invalid_path')
        waited = 0
        while True:
            self.heartbeat()
            delay = slot(self.priority)
            if not delay:
                break
            if waited >= 65:
                raise APIError('rate_limited', delay)
            self.sleep(min(delay, 2))
            waited += min(delay, 2)
        headers = {'X-Api-Key': self.key, 'Content-Type': 'application/json'}
        try:
            response = self.session.request(method, ROOT + path, params=params, headers=headers,
                data=(serialized if serialized is not None else wire(body)) .encode('utf-8') if body is not None or serialized is not None else None,
                timeout=(5, 75), allow_redirects=False)
        except requests.Timeout:
            raise APIError('network_timeout', 15) from None
        except requests.RequestException:
            raise APIError('network', 15) from None
        try:
            if response.status_code == 429:
                retry = str(response.headers.get('Retry-After', '60'))
                delay = min(3600, max(60, int(retry))) if retry.isdecimal() else 60
                block(delay)
                raise APIError('rate_limited', delay)
            if response.status_code in (401, 403):
                raise APIError('authentication')
            if response.status_code >= 500:
                raise APIError('upstream', 15)
            if response.status_code == 404:
                raise APIError('not_found')
            if response.status_code != 200:
                raise APIError('request_rejected')
            if len(response.content) > 8 * 1024 * 1024:
                raise APIError('response_size')
            try:
                payload = response.json(parse_float=Decimal)
            except (ValueError, TypeError):
                raise APIError('invalid_json') from None
            if not isinstance(payload, dict):
                raise APIError('invalid_response')
            if payload.get('ok') is False:
                category = payload.get('error')
                raise APIError(category if category in BUSINESS_ERRORS else 'request_rejected')
            return payload
        finally:
            response.close()

    def balance(self):
        return self.request('GET', 'balance')

    def products(self, page=1):
        return self.request('GET', 'products', params={'page': page})

    def search(self, query, platform='playstation', region=None):
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 150 or platform not in ('playstation', 'xbox', 'steam'):
            raise APIError('invalid_search')
        if platform == 'playstation' and region is not None and region not in ('turkey', 'sng', 'india', 'poland', 'indonesia', 'usa'):
            raise APIError('invalid_search')
        params = {'q': query.strip(), 'platform': platform}
        if region is not None:
            params['region'] = region
        return self.request('GET', 'products/search', params=params)

    def product(self, product_id):
        return self.request('GET', 'products/' + identifier(product_id))

    def steam_check(self, login):
        if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9_]{2,64}', login):
            raise APIError('bad_login')
        return self.request('GET', 'steam-check', params={'login': login})

    def quote(self, body):
        return self.request('POST', 'quotes', body=body)

    def order(self, order_id):
        return self.request('GET', 'orders/' + identifier(order_id))

    def orders(self, *, page=1, client_order_id=None):
        params = {'page': page}
        if client_order_id:
            identifier(client_order_id)
            params['client_order_id'] = client_order_id
        return self.request('GET', 'orders', params=params)

    def purchase(self, serialized):
        # Разрешение реальных покупок проверяется ещё раз прямо у сетевой границы.
        from digital_shop.models import ShopConfig, PurchaseIntent, ShopChat
        from digital_sales.models import BuyerBalanceChat, Supplier
        config = ShopConfig.objects.filter(pk=1, enabled=True, purchases_enabled=True).first()
        if not config:
            raise APIError('purchases_disabled')
        if not isinstance(serialized, str):
            raise APIError('invalid_payload')
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        intent = PurchaseIntent.objects.filter(body_hash=digest, state__in=('submitting', 'uncertain'),
            lease_until__gt=timezone.now(), owner__isnull=False).select_related('cart').first()
        if (intent is None or not ShopChat.objects.filter(binding_id=intent.cart.chat_id, enabled=True).exists() or
                not BuyerBalanceChat.objects.filter(pk=intent.cart.chat_id, buyer_id=intent.cart.buyer_id).exists() or
                any(intent.cart.chat_id in row.chat_ids for row in Supplier.objects.all())):
            raise APIError('purchase_intent_required')
        return self.request('POST', 'orders', serialized=serialized)

    def replace_account(self, order_id, account_id, body):
        return self.request('PUT', 'orders/' + identifier(order_id) + '/accounts/' + identifier(account_id), body=body)

    def close(self):
        self.session.close()
