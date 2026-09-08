import json
import logging
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


logger = logging.getLogger("gamebat.business")

HEADER_RATE_SYMBOLS = ("USDT/RUB", "AED/RUB", "USD/AED")
FRESH_CACHE_KEY = "rapira:header-rates:fresh:v1"
LAST_SUCCESS_CACHE_KEY = "rapira:header-rates:last-success:v1"
REFRESH_LOCK_KEY = "rapira:header-rates:refresh-lock:v1"


class RapiraAPIError(RuntimeError):
    """Ожидаемая ошибка публичного market endpoint Rapira."""


def _number(value, *, allow_negative=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or (number < 0 and not allow_negative):
        return None
    return format(number, "f")


def fetch_market_rates(symbols=HEADER_RATE_SYMBOLS):
    """Получает из Rapira только запрошенные пары и поля close/change."""
    request = Request(
        settings.RAPIRA_MARKET_RATES_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=settings.RAPIRA_API_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status < 200 or status >= 300:
                raise RapiraAPIError(f"Rapira вернула HTTP {status}")
            raw_body = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RapiraAPIError("Не удалось получить котировки Rapira") from exc

    try:
        payload = json.loads(raw_body.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RapiraAPIError("Rapira вернула некорректный JSON") from exc

    if not isinstance(payload, dict):
        raise RapiraAPIError("Ответ Rapira не является объектом")
    if "code" in payload and payload["code"] not in (0, "0", Decimal("0")):
        raise RapiraAPIError("Rapira вернула ошибочный code")
    if not isinstance(payload.get("data"), list):
        raise RapiraAPIError("В ответе Rapira отсутствует массив data")

    requested = tuple(symbols)
    rates = {symbol: {"value": None, "change": None} for symbol in requested}
    for item in payload["data"]:
        if not isinstance(item, dict) or item.get("symbol") not in rates:
            continue
        value = _number(item.get("close"))
        if value is None:
            continue
        rates[item["symbol"]] = {
            "value": value,
            "change": _number(item.get("change"), allow_negative=True),
        }
    return rates


def _unavailable_snapshot():
    return {
        "rates": {symbol: {"value": None, "change": None} for symbol in HEADER_RATE_SYMBOLS},
        "updated_at": None,
        "available": False,
        "stale": False,
    }


def get_cached_market_rates():
    """Возвращает общий 15-секундный кэш, сохраняя последний успешный ответ."""
    cached = cache.get(FRESH_CACHE_KEY)
    if cached is not None:
        return cached

    lock_timeout = max(1, int(settings.RAPIRA_API_TIMEOUT_SECONDS) + 1)
    if not cache.add(REFRESH_LOCK_KEY, True, timeout=lock_timeout):
        previous = cache.get(LAST_SUCCESS_CACHE_KEY)
        return {**previous, "stale": True} if previous is not None else _unavailable_snapshot()

    try:
        rates = fetch_market_rates()
        snapshot = {
            "rates": rates,
            "updated_at": timezone.now().isoformat(),
            "available": True,
            "stale": False,
        }
        cache.set(FRESH_CACHE_KEY, snapshot, timeout=settings.RAPIRA_RATES_CACHE_TTL_SECONDS)
        cache.set(LAST_SUCCESS_CACHE_KEY, snapshot, timeout=None)
        return snapshot
    except RapiraAPIError as exc:
        logger.warning("Котировки Rapira временно недоступны: %s", exc)
        previous = cache.get(LAST_SUCCESS_CACHE_KEY)
        fallback = (
            {**previous, "stale": True}
            if previous is not None
            else _unavailable_snapshot()
        )
        # Короткий negative cache не допускает лавины повторных запросов при сбое.
        cache.set(FRESH_CACHE_KEY, fallback, timeout=settings.RAPIRA_RATES_CACHE_TTL_SECONDS)
        return fallback
    finally:
        cache.delete(REFRESH_LOCK_KEY)
