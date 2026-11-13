"""Только документированный GET /products; покупок, расчётов корзины и произвольных URL нет."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import time
import requests
from core.external_policy import require_live_operation
from .classification import code_characteristics

BASE_URL = 'https://yanstore.ru/api/external/v2/products'
CODE_URL = 'https://yanstore.ru/api/external/v1/codes-catalog'
# Каталог v2 у поставщика может считаться дольше 30 секунд. Один запрос
# ограничен временем короче двухминутной аренды задания и не повторяется скрыто.
PRODUCT_TIMEOUT = (5, 75)


class APIError(Exception):
    def __init__(self, category, retry_after=0):
        self.category, self.retry_after = category, retry_after
        super().__init__(category)  # Ни URL с ключом, ни тело ответа не попадают в исключение.


@dataclass(frozen=True)
class Offer:
    identity: str
    name: str
    kind: str
    platform: str
    region: str
    cost: Decimal | None
    currency: str
    available: bool | None
    attributes: dict


def amount(value):
    try:
        if isinstance(value, (bool, float)):
            raise ValueError
        result = Decimal(str(value))
        if not result.is_finite() or not 0 <= result < Decimal('1e18') or result != result.quantize(Decimal('.01')):
            raise ValueError
        return result.quantize(Decimal('.01'))
    except (ValueError, TypeError, InvalidOperation):
        raise APIError('invalid_amount') from None


def parse_page(payload, number):
    if (not isinstance(payload, dict) or type(payload.get('page')) is not int or payload['page'] != number
            or type(payload.get('has_more')) is not bool or not isinstance(payload.get('items'), list)
            or len(payload['items']) > 50 or payload['has_more'] and not payload['items']):
        raise APIError('invalid_page')
    result = []
    for row in payload['items']:
        if not isinstance(row, dict) or not all(k in row for k in ('product_id', 'name', 'type', 'price', 'currency', 'available')):
            raise APIError('invalid_offer')
        identity, name, kind, currency = (row[k] for k in ('product_id', 'name', 'type', 'currency'))
        if (not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identity)
                or not isinstance(name, str) or not 1 <= len(name.strip()) <= 500
                or not isinstance(kind, str) or not re.fullmatch(r'[a-z_]{1,40}', kind)
                or not isinstance(currency, str) or not re.fullmatch(r'[A-Za-z]{3,8}', currency)
                or row['available'] is not None and type(row['available']) is not bool):
            raise APIError('invalid_offer')
        platform = '' if row.get('platform') is None else row['platform']
        region = '' if row.get('region') is None else row['region']
        if not isinstance(platform, str) or len(platform) > 60 or not isinstance(region, str) or len(region) > 80:
            raise APIError('invalid_offer')
        # Метаданные могут быть пустыми; неизвестные реквизиты и URL не сохраняем.
        meta = row.get('metadata') or {}
        attrs = {'topup_currency': str(meta['topup_currency'])[:8]} if isinstance(meta, dict) and meta.get('topup_currency') else {}
        requirements = row.get('requirements') or {}
        if isinstance(requirements, dict) and 'account_modes' in requirements:
            modes = requirements['account_modes']
            if not isinstance(modes, list) or any(mode not in ('existing', 'new') for mode in modes):
                raise APIError('invalid_offer')
            attrs['account_modes'] = list(dict.fromkeys(modes))
        result.append(Offer(identity, name.strip(), kind, platform, region,
            None if row['price'] is None else amount(row['price']), currency.upper(), row['available'], attrs))
    return result, payload['has_more']


def parse_codes(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list) or len(payload['items']) > 20000:
        raise APIError('invalid_codes')
    currency = payload.get('currency')
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Za-z]{3,8}', currency):
        raise APIError('invalid_codes')
    result, seen = [], set()
    for row in payload['items']:
        if not isinstance(row, dict):
            raise APIError('invalid_codes')
        identity, name, category, stock = (row.get(field) for field in ('item_id', 'name', 'category', 'in_stock'))
        if (type(identity) is not int or identity <= 0 or identity in seen or
                not isinstance(name, str) or not 1 <= len(name.strip()) <= 500 or
                not isinstance(category, str) or not 1 <= len(category.strip()) <= 120 or
                type(stock) is not int or stock < 0):
            raise APIError('invalid_codes')
        seen.add(identity)
        region, attrs = code_characteristics(name, category)
        # ID v1 имеет собственное пространство. Непрозрачные pv2_ID не изобретаются.
        result.append(Offer(f'v1_code_{identity}', name.strip(), 'code', attrs['family'], region,
            None if row.get('price') is None else amount(row['price']), currency.upper(), stock > 0, attrs))
    return result


class CatalogClient:
    def __init__(self, key, session=None, sleeper=time.sleep):
        require_live_operation('digital_prices_api')
        self._key, self.session, self.sleep = key, session or requests.Session(), sleeper

    def fetch(self, heartbeat=lambda: None, *, include_codes=False):
        require_live_operation('digital_prices_api')
        result, seen = [], set()
        for page in range(1, 1001):
            heartbeat()
            if page > 1:
                self.sleep(3.2)  # Общий документированный предел — 20 запросов в минуту.
            try:
                response = self.session.get(BASE_URL, params={'page': page}, headers={'X-Api-Key': self._key},
                    timeout=PRODUCT_TIMEOUT, allow_redirects=False)
            except requests.Timeout:
                raise APIError('network_timeout', 60) from None
            except requests.RequestException:
                raise APIError('network', 60) from None
            try:
                if response.status_code in (401, 403):
                    raise APIError('authentication')
                if response.status_code == 429:
                    delay = str(response.headers.get('Retry-After', '60'))
                    raise APIError('rate_limited', max(60, min(3600, int(delay))) if delay.isdecimal() else 60)
                if response.status_code >= 500:
                    raise APIError('upstream', 120)
                if response.status_code != 200:
                    raise APIError('http_status')
                if len(response.content) > 8 * 1024 * 1024:
                    raise APIError('response_size')
                try:
                    payload = response.json(parse_float=Decimal)
                except (ValueError, TypeError):
                    raise APIError('invalid_json') from None
                rows, more = parse_page(payload, page)
                for row in rows:
                    if row.identity in seen:
                        raise APIError('duplicate_id')
                    seen.add(row.identity)
                    result.append(row)
                if not more:
                    if not result:
                        raise APIError('empty_catalog')
                    if not include_codes:
                        return result
                    break
            finally:
                response.close()
        else:
            raise APIError('page_limit')
        # V2 фактически не возвращает коды этого магазина. Документированный v1
        # перечисляет весь ассортимент с номиналами и остатком. Одна версия
        # служит владельцем кодов: при появлении кодов v2 дублей не возникнет.
        heartbeat()
        self.sleep(3.2)
        try:
            response = self.session.get(CODE_URL, headers={'X-Api-Key': self._key},
                timeout=(5, 25), allow_redirects=False)
        except requests.RequestException:
            raise APIError('network', 60) from None
        try:
            if response.status_code in (401, 403):
                raise APIError('codes_authentication')
            if response.status_code == 429:
                delay = str(response.headers.get('Retry-After', '60'))
                raise APIError('rate_limited', max(60, min(3600, int(delay))) if delay.isdecimal() else 60)
            if response.status_code >= 500:
                raise APIError('upstream', 120)
            if response.status_code != 200 or len(response.content) > 8 * 1024 * 1024:
                raise APIError('invalid_codes')
            try:
                codes = parse_codes(response.json(parse_float=Decimal))
            except (ValueError, TypeError):
                raise APIError('invalid_codes') from None
            if not codes:
                raise APIError('empty_codes_catalog')
            return [row for row in result if row.kind != 'code'] + codes
        finally:
            response.close()

    def close(self):
        self.session.close()
