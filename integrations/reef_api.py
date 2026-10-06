"""HTTP-клиент ReefAPI. Секрет и тело ответа не попадают в исключения и журналы."""
import requests
from django.core.exceptions import ImproperlyConfigured

from .crypto import decrypt_secret
from .models import ReefApiCredential


class ReefApiError(Exception):
    def __init__(self, message, *, code=""):
        super().__init__(message)
        self.code = code


class ReefApiClient:
    BASE_URL = "https://api.reefapi.com/avito/v1"

    def __init__(self, key=None, transport=None):
        if key is None:
            credential = ReefApiCredential.objects.filter(pk=1).first()
            if not credential or not credential.is_configured:
                raise ReefApiError("Ключ ReefAPI не настроен.")
            try:
                key = decrypt_secret(credential.encrypted_api_key)
            except ImproperlyConfigured as exc:
                raise ReefApiError("Ключ ReefAPI недоступен. Сохраните его повторно в настройках API.") from exc
        self._key = key
        self._transport = transport or requests.post

    def _post(self, action, payload):
        try:
            response = self._transport(
                f"{self.BASE_URL}/{action}",
                headers={"x-api-key": self._key, "content-type": "application/json"},
                json=payload, timeout=(5, 25),
            )
        except requests.Timeout as exc:
            raise ReefApiError("ReefAPI не ответил вовремя. Повторите проверку позже.") from exc
        except requests.RequestException as exc:
            raise ReefApiError("Не удалось подключиться к ReefAPI.") from exc
        if response.status_code in (401, 403):
            raise ReefApiError("Ключ ReefAPI отклонён. Проверьте его в настройках API.")
        if response.status_code == 429:
            raise ReefApiError("Лимит запросов ReefAPI исчерпан. Повторите позже.")
        if response.status_code == 404 and action == "listing":
            raise ReefApiError("Объявление больше не найдено.", code="NOT_FOUND")
        if response.status_code >= 400:
            raise ReefApiError("ReefAPI вернул ошибку. Повторите проверку позже.")
        try:
            envelope = response.json()
        except ValueError as exc:
            raise ReefApiError("ReefAPI вернул некорректный ответ.") from exc
        if isinstance(envelope, dict) and envelope.get("ok") is False:
            detail = envelope.get("error")
            code = str(detail.get("code") or "") if isinstance(detail, dict) else ""
            if action == "listing" and code == "NOT_FOUND":
                raise ReefApiError("Объявление больше не найдено.", code=code)
            if any(marker in code.upper() for marker in ("AUTH", "KEY", "UNAUTHORIZED", "FORBIDDEN")):
                raise ReefApiError("Ключ ReefAPI отклонён. Проверьте его в настройках API.")
        if not isinstance(envelope, dict) or envelope.get("ok") is not True:
            raise ReefApiError("ReefAPI не выполнил запрос. Повторите проверку позже.")
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise ReefApiError("ReefAPI вернул неполные данные.")
        return data

    def search(self, query, page, *, price_max=None):
        payload = {
            "query": query, "location": "all", "sort": "price_asc", "page": page,
            "include_sponsored": True, "include_fallback_results": False,
        }
        if price_max is not None:
            payload["price_max"] = int(price_max)
        data = self._post("search", payload)
        if not isinstance(data.get("listings"), list):
            raise ReefApiError("ReefAPI вернул неполную поисковую выдачу.")
        return data

    def listing(self, ad_id):
        data = self._post("listing", {"ad_id": str(ad_id)})
        if not isinstance(data.get("listing"), dict):
            raise ReefApiError("ReefAPI вернул неполную карточку объявления.")
        return data
