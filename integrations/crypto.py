from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _key() -> bytes:
    configured = str(settings.INTEGRATION_ENCRYPTION_KEY or "").strip()
    if configured:
        return configured.encode("ascii")
    path = Path(settings.INTEGRATION_ENCRYPTION_KEY_FILE)
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        try:
            path.chmod(0o600)
        except OSError:
            pass
    key = path.read_bytes().strip()
    try:
        Fernet(key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("Некорректный ключ шифрования интеграций.") from exc
    return key


def encrypt_secret(value: str) -> str:
    value = str(value or "")
    return Fernet(_key()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return Fernet(_key()).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise ImproperlyConfigured("Не удалось расшифровать параметры интеграции.") from exc
