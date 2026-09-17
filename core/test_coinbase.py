import json
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.services.coinbase import (
    FRESH_CACHE_KEY,
    LAST_SUCCESS_CACHE_KEY,
    CoinbaseAPIError,
    fetch_usdt_aed_rate,
    get_cached_usdt_aed_rate,
)


class FakeResponse:
    def __init__(self, payload=None, *, raw_body=None, status=200):
        self.payload = payload
        self.raw_body = raw_body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.status

    def read(self):
        if self.raw_body is not None:
            return self.raw_body
        return json.dumps(self.payload).encode("utf-8")


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "coinbase-tests"}},
    COINBASE_EXCHANGE_RATES_URL="https://api.coinbase.com/v2/exchange-rates",
    COINBASE_API_TIMEOUT_SECONDS=5,
    COINBASE_RATES_CACHE_TTL_SECONDS=30,
)
class CoinbaseServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("core.services.coinbase.urlopen")
    def test_success_returns_direct_usdt_aed_decimal(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "data": {"currency": "USDT", "rates": {"AED": "3.67251234", "USD": "1.00"}},
        })

        rate = fetch_usdt_aed_rate()

        self.assertEqual(rate, Decimal("3.67251234"))
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.headers["Accept"], "application/json")
        self.assertEqual(parse_qs(urlsplit(request.full_url).query), {"currency": ["USDT"]})
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 5)

    @patch("core.services.coinbase.urlopen")
    def test_missing_aed_is_service_error(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "data": {"currency": "USDT", "rates": {"USD": "1.00"}},
        })

        with self.assertRaisesMessage(CoinbaseAPIError, "отсутствует курс AED"):
            fetch_usdt_aed_rate()

    @patch("core.services.coinbase.urlopen")
    def test_malformed_json_is_service_error(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(raw_body=b"{not-json")

        with self.assertRaisesMessage(CoinbaseAPIError, "некорректный JSON"):
            fetch_usdt_aed_rate()

    @patch("core.services.coinbase.urlopen")
    def test_timeout_uses_last_known_good(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "data": {"currency": "USDT", "rates": {"AED": "3.6725"}},
        })
        get_cached_usdt_aed_rate()
        cache.delete(FRESH_CACHE_KEY)
        mocked_urlopen.side_effect = TimeoutError()

        fallback = get_cached_usdt_aed_rate()

        self.assertEqual(fallback["value"], Decimal("3.6725"))
        self.assertTrue(fallback["stale"])
        self.assertIsNotNone(cache.get(LAST_SUCCESS_CACHE_KEY))
        self.assertEqual(mocked_urlopen.call_count, 2)

    @patch("core.services.coinbase.urlopen")
    def test_http_500_and_429_do_not_retry_aggressively(self, mocked_urlopen):
        for status in (500, 429):
            with self.subTest(status=status):
                cache.clear()
                mocked_urlopen.reset_mock()
                mocked_urlopen.side_effect = HTTPError(
                    "https://api.coinbase.com/v2/exchange-rates",
                    status,
                    "error",
                    None,
                    None,
                )

                first = get_cached_usdt_aed_rate()
                second = get_cached_usdt_aed_rate()

                self.assertFalse(first["available"])
                self.assertEqual(first, second)
                self.assertEqual(mocked_urlopen.call_count, 1)

    @patch("core.services.coinbase.urlopen")
    def test_fresh_cache_prevents_repeated_coinbase_requests(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "data": {"currency": "USDT", "rates": {"AED": "3.6725"}},
        })

        first = get_cached_usdt_aed_rate()
        second = get_cached_usdt_aed_rate()

        self.assertEqual(first, second)
        self.assertEqual(mocked_urlopen.call_count, 1)
        self.assertEqual(first["value"], Decimal("3.6725"))
        self.assertEqual(first["source"], "Coinbase")
