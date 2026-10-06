"""Официальный Partner API: точный JSON, таймаут, запрет редиректа ключа и журнал без PII."""
import json
import re
import time
from datetime import timedelta
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection as database, transaction
from django.db.models import F
from django.utils import timezone

from integrations.crypto import decrypt_secret

CONTRACTS = json.loads(Path(__file__).with_name("contracts.json").read_text("utf-8"))
BASE_URL = "https://api.partner.market.yandex.ru"


def api_key():
    value = settings.YANDEX_MARKET_API_KEY
    if value:
        return value.strip()
    path = Path(settings.YANDEX_MARKET_KEY_FILE)
    return decrypt_secret(path.read_text("utf-8").strip()) if path.exists() else ""


def json_bytes(value):
    """Decimal сериализуется числом JSON без промежуточного float."""
    def encode(item):
        if isinstance(item, Decimal):
            if not item.is_finite():
                raise ValidationError("Число должно быть конечным.")
            return str(item)
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(str(k)) + ":" + encode(v) for k, v in item.items()) + "}"
        if isinstance(item, (list, tuple)):
            return "[" + ",".join(encode(v) for v in item) + "]"
        return json.dumps(item, ensure_ascii=False, allow_nan=False)
    return encode(value).encode("utf-8")


def safe_message(value, secret=""):
    value = str(value)
    if secret:
        value = value.replace(secret, "[скрыто]")
    value = re.sub(r"(?i)(api[-_ ]?key|authorization|cookie|token)\s*[:=]\s*[^\s,;]+", r"\1=[скрыто]", value)
    return value[:1500]


@dataclass
class MarketError(Exception):
    message: str
    code: str = "API_ERROR"
    status: int | None = None
    retryable: bool = False
    retry_after: int = 0

    def __str__(self):
        return self.message


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class YandexMarketClient:
    def __init__(self, integration=None, *, key=None, job=None, actor=None, transport=None):
        self.integration = integration
        self.key = api_key() if key is None else key
        self.job = job
        self.actor = actor or (job.actor if job else None)
        self.transport = transport or build_opener(NoRedirect()).open

    def reserve_budget(self, operation, contract, body):
        from .models import ApiBudget
        limits = contract.get("limits", {})
        rule = limits.get("none", {})
        if not rule.get("amount"):
            return
        seconds = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}.get(rule.get("period"), 60) * rule.get("period-duration", 1)
        amount = rule["amount"]
        units = 1
        path = limits.get("path", "")
        if path.startswith("req."):
            value = body or {}
            for part in path[4:].split("."):
                value = value.get(part, []) if isinstance(value, dict) else []
            units = max(1, len(value)) if isinstance(value, list) else 1
        key = f"{self.integration.business_id if self.integration else 'key'}:{operation}"
        now = timezone.now()
        with transaction.atomic():
            # Первая запись сериализует резервирование также в SQLite.
            ApiBudget.objects.filter(pk=key).update(used=F("used"))
            ApiBudget.objects.get_or_create(key=key)
            budget = ApiBudget.objects.select_for_update().get(pk=key)
            if budget.window_start + timedelta(seconds=seconds) <= now:
                budget.window_start, budget.used = now, 0
            if budget.used + units > amount:
                delay = max(1, int((budget.window_start + timedelta(seconds=seconds) - now).total_seconds()) + 1)
                raise MarketError("Достигнут лимит API. Обмен продолжится автоматически.", "LOCAL_RATE_LIMIT", retryable=True, retry_after=delay)
            budget.used += units
            budget.save(update_fields=["window_start", "used"])

    def call(self, operation, *, body=None, params=None, query=None, pdf=False, entity_id=""):
        if database.in_atomic_block and not getattr(settings, "YANDEX_MARKET_ALLOW_TEST_TRANSACTION", False):
            raise RuntimeError("Сетевой запрос Маркета запрещён внутри транзакции CRM.")
        if not self.key:
            raise MarketError("API-Key Яндекс Маркета не настроен.", "MISSING_KEY")
        contract = CONTRACTS[operation]
        self.reserve_budget(operation, contract, body)
        values = dict(params or {})
        if self.integration:
            values.setdefault("businessId", self.integration.business_id)
            values.setdefault("campaignId", self.integration.campaign_id)
        path = contract["path"].format(**{k: quote(str(v), safe="") for k, v in values.items()})
        url = BASE_URL + path
        if query:
            url += "?" + urlencode(query, doseq=True)
        request = Request(url, method=contract["method"], data=json_bytes(body) if body is not None else None,
                          headers={"Api-Key": self.key, "Accept": "application/pdf" if pdf else "application/json", "Content-Type": "application/json"})
        started = time.monotonic()
        status, request_id, error = None, "", None
        try:
            try:
                response = self.transport(request, timeout=settings.YANDEX_MARKET_TIMEOUT)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.status if hasattr(response, "status") else response.code
                request_id = safe_message(response.headers.get("X-Request-Id", ""), self.key)[:200]
                raw = response.read(30 * 1024 * 1024 + 1)
                retry_after = response.headers.get("Retry-After", "")
            if len(raw) > 30 * 1024 * 1024:
                raise MarketError("Ответ Маркета превысил допустимый размер.", "RESPONSE_TOO_LARGE", status)
            if pdf and status == 200 and raw.startswith(b"%PDF-"):
                return raw
            try:
                data = json.loads(raw, parse_float=Decimal)
            except (ValueError, UnicodeError):
                raise MarketError("Маркет вернул ответ неожиданного формата.", "INVALID_RESPONSE", status, status >= 500)
            if not isinstance(data, dict):
                raise MarketError("Маркет вернул ответ неожиданного формата.", "INVALID_RESPONSE", status)
            errors = list(data.get("errors") or [])
            for result in data.get("results") or []:
                errors.extend(result.get("errors") or [])
            if status >= 400 or data.get("status") == "ERROR" or errors:
                codes = ", ".join(str(e.get("code", "API_ERROR")) for e in errors if isinstance(e, dict))
                messages = "; ".join(str(e.get("message", e.get("comment", ""))) for e in errors if isinstance(e, dict))
                retryable = status in (420, 429, 500, 502, 503, 504)
                raise MarketError(safe_message(messages or f"Ошибка API Маркета (HTTP {status}).", self.key),
                                  safe_message(codes or "API_ERROR", self.key)[:100], status, retryable,
                                  min(3600, int(retry_after)) if retry_after.isdigit() else 0)
            if pdf:
                raise MarketError("Маркет не вернул официальный PDF.", "INVALID_PDF", status)
            return data
        except MarketError as exc:
            error = exc
            raise
        except (URLError, TimeoutError, OSError) as exc:
            error = MarketError("Не удалось связаться с Яндекс Маркетом. Запрос будет повторён.", "NETWORK", None, True)
            raise error from None
        finally:
            from .models import ApiLog, SyncJob
            ApiLog.objects.create(
                integration=self.integration, operation=operation, entity_id=str(entity_id)[:255],
                method=contract["method"], endpoint=path, http_status=status,
                result="error" if error else "success", error_code=error.code if error else "",
                message=str(error) if error else "", request_id=request_id,
                duration_ms=int((time.monotonic() - started) * 1000), job=self.job, actor=self.actor,
                attempt=self.job.attempts if self.job else 0,
            )
            if self.job:
                SyncJob.objects.filter(pk=self.job.pk, lease=self.job.lease).update(updated_at=timezone.now())

    def pages(self, operation, *, body=None, key, params=None, limit=50):
        token, seen = None, set()
        while True:
            query = {"limit": limit}
            if token:
                query["pageToken"] = token
            data = self.call(operation, body=body, params=params, query=query)
            result = data.get("result", data)
            yield from result.get(key, [])
            token = result.get("paging", {}).get("nextPageToken")
            if not token:
                break
            if token in seen:
                raise MarketError("Маркет повторил токен страницы. Каталог получен не полностью.", "PAGINATION_LOOP")
            seen.add(token)

    def order(self, order_id):
        data = self.call("getBusinessOrders", body={"campaignIds": [self.integration.campaign_id], "orderIds": [int(order_id)]})
        orders = data.get("orders", [])
        for order in orders:
            if order.get("orderId") == int(order_id) and order.get("campaignId") == self.integration.campaign_id:
                return order
        raise MarketError("Заказ не найден в выбранном FBS-магазине.", "ORDER_NOT_FOUND")
