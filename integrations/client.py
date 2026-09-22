import json
import time
from dataclasses import dataclass
from urllib import error, parse, request

from django.conf import settings
from django.core.cache import cache

from .crypto import decrypt_secret
from .models import IntegrationCredential


@dataclass
class AvitoAPIError(Exception):
    message: str
    category: str = "permanent"
    status: int | None = None
    retry_after: int | None = None

    def __str__(self):
        return self.message

    @property
    def retryable(self):
        return self.category in {"rate_limit", "temporary", "network"}


class AvitoClient:
    """Единый HTTP-клиент. Токены, секреты и полные ответы никогда не логируются."""

    def __init__(self, credential=None):
        self.credential = credential or IntegrationCredential.objects.get(
            provider=IntegrationCredential.Provider.AVITO
        )
        self.base_url = settings.AVITO_API_BASE_URL.rstrip("/")
        self.timeout = settings.AVITO_API_TIMEOUT_SECONDS

    def _decode(self, response):
        raw = response.read()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AvitoAPIError("Avito вернул некорректный ответ.", "temporary", response.status) from exc

    def _execute(self, req, *, retry_network=False):
        # GET не меняет состояние Avito; получение OAuth-токена также можно повторить.
        # Запросы изменения цены и остатка здесь намеренно не повторяются.
        attempts = 5 if req.get_method() == "GET" else 3 if retry_network else 1
        for attempt in range(attempts):
            try:
                with request.urlopen(req, timeout=self.timeout) as response:
                    return self._decode(response)
            except error.HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get("Retry-After")
                try:
                    retry_after = int(retry_after) if retry_after else None
                except ValueError:
                    retry_after = None
                if status in {401, 403}:
                    category, message = "auth", "Avito отклонил доступ к этому методу."
                elif status == 429:
                    category, message = "rate_limit", "Превышен лимит запросов Avito."
                elif status in {400, 404, 409, 422}:
                    category, message = "validation", "Avito отклонил данные запроса."
                elif status >= 500:
                    category, message = "temporary", "Сервис Avito временно недоступен."
                else:
                    category, message = "permanent", "Avito не выполнил запрос."
                raise AvitoAPIError(message, category, status, retry_after) from exc
            except (error.URLError, TimeoutError, OSError) as exc:
                if attempt < attempts - 1:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                reason = exc.reason if isinstance(exc, error.URLError) else exc
                message = (
                    "Истекло время ожидания ответа Avito."
                    if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower()
                    else "Нет соединения с Avito."
                )
                raise AvitoAPIError(message, "network") from exc

    def _token(self):
        cache_key = f"avito-token-{self.credential.pk}-{self.credential.updated_at.timestamp()}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        payload = parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": decrypt_secret(self.credential.encrypted_client_id),
            "client_secret": decrypt_secret(self.credential.encrypted_client_secret),
        }).encode("ascii")
        req = request.Request(
            f"{self.base_url}/token", data=payload, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = self._execute(req, retry_network=True)
        token = data.get("access_token")
        if not token:
            raise AvitoAPIError("Avito не вернул access token.", "auth")
        ttl = max(60, int(data.get("expires_in") or 3600) - 60)
        cache.set(cache_key, token, ttl)
        return token

    def request_json(self, method, path, *, payload=None, query=None, retry_network=False):
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            url, data=body, method=method,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        return self._execute(req, retry_network=retry_network)

    def get_self(self):
        return self.request_json("GET", "/core/v1/accounts/self")

    def list_items(self, *, page=1, per_page=100):
        return self.request_json("GET", "/core/v1/items", query={"page": page, "per_page": per_page})

    def find_item(self, item_id):
        item_id = int(item_id)
        for page in range(1, 101):
            data = self.list_items(page=page, per_page=100)
            resources = data.get("resources") or []
            for item in resources:
                if int(item.get("id") or 0) == item_id:
                    return item
            if len(resources) < 100:
                break
        raise AvitoAPIError("Объявление больше не найдено в аккаунте Avito.", "validation", 404)

    def get_item_details(self, account_id, item_id):
        return self.request_json("GET", f"/core/v1/accounts/{account_id}/items/{item_id}/")

    def get_category_tree(self):
        return self.request_json("GET", "/autoload/v1/user-docs/tree")

    def get_category_fields(self, category_slug):
        safe_slug = parse.quote(str(category_slug), safe="")
        return self.request_json("GET", f"/autoload/v1/user-docs/node/{safe_slug}/fields")

    def get_autoload_profile(self):
        return self.request_json("GET", "/autoload/v2/profile")

    def get_stocks(self, item_ids, *, strong_consistency=True):
        return self.request_json(
            "POST", "/stock-management/1/info",
            payload={"item_ids": [int(value) for value in item_ids], "strong_consistency": strong_consistency},
            retry_network=True,  # Это только чтение, повтор запроса не меняет Avito.
        )

    def update_stock(self, item_id, quantity):
        # Официальный Stock Management contract: stocks[].item_id + quantity (0..999999).
        return self.request_json(
            "PUT", "/stock-management/1/stocks",
            payload={"stocks": [{"item_id": int(item_id), "quantity": int(quantity)}]},
        )

    def update_price(self, item_id, price):
        # Официальный Item API: POST /core/v1/items/{item_id}/update_price.
        return self.request_json(
            "POST", f"/core/v1/items/{int(item_id)}/update_price", payload={"price": int(price)}
        )
