"""Настройки ключа ReefAPI в существующем хранилище интеграций."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from .crypto import encrypt_secret
from .models import AvitoListingConnection, ReefApiCredential
from .reef_api import ReefApiClient, ReefApiError


def save_key(value):
    value = str(value or "").strip()
    if not value:
        raise ValidationError("Введите API key ReefAPI.")
    credential, _ = ReefApiCredential.objects.get_or_create(pk=1)
    credential.encrypted_api_key = encrypt_secret(value)
    credential.last_error = ""
    credential.save(update_fields=("encrypted_api_key", "last_error", "updated_at"))
    return credential


def check_connection():
    credential = ReefApiCredential.objects.filter(pk=1).first()
    if not credential or not credential.is_configured:
        raise ReefApiError("Ключ ReefAPI не настроен.")
    client = ReefApiClient()
    own_ad = AvitoListingConnection.objects.values_list("remote_listing__avito_item_id", flat=True).first()
    try:
        if own_ad:
            client.listing(own_ad)
        else:
            client.search("PlayStation 5", 1)
    except ReefApiError as exc:
        credential.last_error = str(exc)
        credential.last_checked_at = timezone.now()
        credential.save(update_fields=("last_error", "last_checked_at", "updated_at"))
        raise
    credential.last_error = ""
    credential.last_checked_at = timezone.now()
    credential.save(update_fields=("last_error", "last_checked_at", "updated_at"))
    return credential
