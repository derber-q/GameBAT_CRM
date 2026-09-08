import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.services.rapira import (
    FRESH_CACHE_KEY,
    LAST_SUCCESS_CACHE_KEY,
    RapiraAPIError,
    fetch_market_rates,
    get_cached_market_rates,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "rapira-tests"}},
    RAPIRA_MARKET_RATES_URL="https://api.rapira.net/open/market/rates",
    RAPIRA_API_TIMEOUT_SECONDS=4,
    RAPIRA_RATES_CACHE_TTL_SECONDS=15,
)
class RapiraServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("core.services.rapira.urlopen")
    def test_success_uses_close_and_returns_only_requested_symbols(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "code": 0,
            "data": [
                {"symbol": "USDT/RUB", "close": 87.89, "change": 0.49},
                {"symbol": "BTC/USDT", "close": 79040.5, "change": -1328.5},
            ],
        })

        rates = fetch_market_rates(("USDT/RUB",))

        self.assertEqual(rates, {"USDT/RUB": {"value": "87.89", "change": "0.49"}})
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.headers["Accept"], "application/json")
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 4)

    @patch("core.services.rapira.urlopen")
    def test_missing_pair_has_no_invented_value(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "code": 0,
            "data": [{"symbol": "USDT/RUB", "close": 87.89, "change": 0.49}],
        })

        rates = fetch_market_rates(("USD/RUB", "AED/RUB"))

        self.assertIsNone(rates["USD/RUB"]["value"])
        self.assertIsNone(rates["AED/RUB"]["value"])

    @patch("core.services.rapira.urlopen")
    def test_invalid_response_is_reported_as_service_error(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({"code": 1, "data": []})

        with self.assertRaises(RapiraAPIError):
            fetch_market_rates()

    @patch("core.services.rapira.urlopen")
    def test_fresh_cache_prevents_repeated_rapira_requests(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({"code": 0, "data": []})

        first = get_cached_market_rates()
        second = get_cached_market_rates()

        self.assertEqual(first, second)
        self.assertEqual(mocked_urlopen.call_count, 1)

    @patch("core.services.rapira.urlopen")
    def test_timeout_keeps_last_successful_values(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse({
            "code": 0,
            "data": [{"symbol": "USDT/RUB", "close": 87.89, "change": 0.49}],
        })
        get_cached_market_rates()
        cache.delete(FRESH_CACHE_KEY)
        mocked_urlopen.side_effect = TimeoutError()

        fallback = get_cached_market_rates()

        self.assertTrue(fallback["stale"])
        self.assertEqual(fallback["rates"]["USDT/RUB"]["value"], "87.89")
        self.assertIsNotNone(cache.get(LAST_SUCCESS_CACHE_KEY))

    @patch("core.views.get_cached_market_rates")
    def test_internal_endpoint_returns_compact_payload_without_browser_cache(self, mocked_rates):
        mocked_rates.return_value = {
            "rates": {"USDT/RUB": {"value": "87.89", "change": "0.49"}},
            "updated_at": "2026-09-07T09:00:00+00:00",
            "available": True,
            "stale": False,
        }
        user = get_user_model().objects.create_user("rates-user", password="StrongPass!123")
        self.client.force_login(user)

        response = self.client.get(reverse("core:exchange_rates"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "Rapira")
        self.assertEqual(response.json()["rates"]["USDT/RUB"]["value"], "87.89")
        self.assertEqual(response["Cache-Control"], "no-store, max-age=0")
