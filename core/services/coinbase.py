import json
import logging
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


logger = logging.getLogger("gamebat.business")

FRESH_CACHE_KEY = "coinbase:usdt-aed:fresh:v1"
LAST_SUCCESS_CACHE_KEY = "coinbase:usdt-aed:last-success:v1"
REFRESH_LOCK_KEY = "coinbase:usdt-aed:refresh-lock:v1"


class CoinbaseAPIError(RuntimeError):
    """Ожидаемая ошибка публичного Coinbase Exchange Rates endpoint."""


def _exchange_rates_url():
    parts = urlsplit(settings.COINBASE_EXCHANGE_RATES_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["currency"] = "USDT"
    return urlunsplit(parts._replace(query=urlencode(query)))


def fetch_usdt_aed_rate():
    """Получает прямой курс: количество AED за один USDT."""
    request = Request(
        _exchange_rates_url(),
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=settings.COINBASE_API_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status < 200 or status >= 300:
                raise CoinbaseAPIError(f"Coinbase вернула HTTP {status}")
            raw_body = response.read()
    except HTTPError as exc:
        raise CoinbaseAPIError(f"Coinbase вернула HTTP {exc.code}") from exc
    except TimeoutError as exc:
        raise CoinbaseAPIError("Истекло время ожидания ответа Coinbase") from exc
    except (URLError, OSError) as exc:
        raise CoinbaseAPIError("Не удалось получить курс Coinbase") from exc

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoinbaseAPIError("Coinbase вернула некорректный JSON") from exc

    if not isinstance(payload, dict):
        raise CoinbaseAPIError("Ответ Coinbase не является объектом")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise CoinbaseAPIError("В ответе Coinbase отсутствует объект data")
    if data.get("currency") != "USDT":
        raise CoinbaseAPIError("Coinbase вернула неожиданную базовую валюту")
    rates = data.get("rates")
    if not isinstance(rates, dict):
        raise CoinbaseAPIError("В ответе Coinbase отсутствует объект rates")
    if "AED" not in rates:
        raise CoinbaseAPIError("В ответе Coinbase отсутствует курс AED")
    value = rates["AED"]
    if value is None or isinstance(value, bool):
        raise CoinbaseAPIError("Coinbase вернула некорректный курс AED")
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CoinbaseAPIError("Coinbase вернула некорректный курс AED") from exc
    if not rate.is_finite() or rate <= 0:
        raise CoinbaseAPIError("Coinbase вернула неположительный курс AED")
    return rate


def _unavailable_snapshot():
    return {
        "value": None,
        "updated_at": None,
        "available": False,
        "stale": False,
        "source": "Coinbase",
    }


def get_cached_usdt_aed_rate():
    """Возвращает 30-секундный cache курса и сохраняет last-known-good."""
    cached = cache.get(FRESH_CACHE_KEY)
    if cached is not None:
        return cached

    lock_timeout = max(1, int(settings.COINBASE_API_TIMEOUT_SECONDS) + 1)
    if not cache.add(REFRESH_LOCK_KEY, True, timeout=lock_timeout):
        previous = cache.get(LAST_SUCCESS_CACHE_KEY)
        return {**previous, "stale": True} if previous is not None else _unavailable_snapshot()

    try:
        rate = fetch_usdt_aed_rate()
        snapshot = {
            "value": rate,
            "updated_at": timezone.now().isoformat(),
            "available": True,
            "stale": False,
            "source": "Coinbase",
        }
        cache.set(FRESH_CACHE_KEY, snapshot, timeout=settings.COINBASE_RATES_CACHE_TTL_SECONDS)
        cache.set(LAST_SUCCESS_CACHE_KEY, snapshot, timeout=None)
        return snapshot
    except CoinbaseAPIError as exc:
        logger.warning("Курс USDT/AED Coinbase временно недоступен: %s", exc)
        previous = cache.get(LAST_SUCCESS_CACHE_KEY)
        fallback = (
            {**previous, "stale": True}
            if previous is not None
            else _unavailable_snapshot()
        )
        # Negative cache предотвращает быстрые повторные запросы после сбоя.
        cache.set(FRESH_CACHE_KEY, fallback, timeout=settings.COINBASE_RATES_CACHE_TTL_SECONDS)
        return fallback
    finally:
        cache.delete(REFRESH_LOCK_KEY)
