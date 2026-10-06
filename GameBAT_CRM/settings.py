"""Настройки ReSOURCE: локальная SQLite, серверные шаблоны и интеграция Avito."""
import os
import time
from pathlib import Path

from django.core.management.utils import get_random_secret_key
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# В репозитории нет фиксированного секрета. Локальный ключ хранится в игнорируемом
# файле, а production должен передавать DJANGO_SECRET_KEY через окружение.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    local_secret_path = BASE_DIR / ".django-secret-key"
    if local_secret_path.exists():
        SECRET_KEY = local_secret_path.read_text(encoding="utf-8").strip()
    else:
        SECRET_KEY = get_random_secret_key()
        local_secret_path.write_text(SECRET_KEY, encoding="utf-8")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,192.168.0.101"
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "catalog",
    "partners",
    "warehouse",
    "supplies",
    "consignment",
    "pricing",
    "sales",
    "cash",
    "creditors",
    "price",
    "orders",
    "integrations.apps.IntegrationsConfig",
    "yandex_market.apps.YandexMarketConfig",
    "resource_storefront.apps.ResourceStorefrontConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "GameBAT_CRM.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.crm_header",
                "resource_storefront.context_processors.storefront_context",
            ],
        },
    },
]
WSGI_APPLICATION = "GameBAT_CRM.wsgi.application"
ASGI_APPLICATION = "GameBAT_CRM.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # Сайт и фоновые обработчики пишут в один SQLite-файл. WAL не блокирует
        # чтение на время записи, а IMMEDIATE захватывает право записи в начале
        # atomic-блока и ждёт timeout вместо ошибки при переходе read -> write.
        "OPTIONS": {
            "timeout": 30,
            "transaction_mode": "IMMEDIATE",
            "init_command": (
                "PRAGMA journal_mode=WAL; "
                "PRAGMA synchronous=NORMAL; "
                "PRAGMA busy_timeout=30000"
            ),
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "protected_media"
MEDIA_URL = "/protected-media/"
INTEGRATION_ENCRYPTION_KEY = os.environ.get("INTEGRATION_ENCRYPTION_KEY", "")
INTEGRATION_ENCRYPTION_KEY_FILE = BASE_DIR / ".integration-encryption-key"
def _resource_token_encryption_key():
    configured = os.environ.get("RESOURCE_TOKEN_ENCRYPTION_KEY", "").strip()
    key_path = Path(os.environ.get(
        "RESOURCE_TOKEN_ENCRYPTION_KEY_FILE",
        BASE_DIR / ".resource-token-encryption-key",
    ))
    if not configured:
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            for _ in range(40):
                configured = key_path.read_text(encoding="ascii").strip()
                try:
                    Fernet(configured.encode("ascii"))
                    break
                except (ValueError, UnicodeEncodeError):
                    time.sleep(0.05)
        else:
            configured = Fernet.generate_key().decode("ascii")
            with os.fdopen(descriptor, "w", encoding="ascii") as key_file:
                key_file.write(configured)
                key_file.flush()
                os.fsync(key_file.fileno())
    try:
        Fernet(configured.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise ImproperlyConfigured("RESOURCE_TOKEN_ENCRYPTION_KEY must be a Fernet URL-safe base64 key") from None
    return configured


RESOURCE_TOKEN_ENCRYPTION_KEY = _resource_token_encryption_key()
AVITO_API_BASE_URL = "https://api.avito.ru"
AVITO_API_TIMEOUT_SECONDS = int(os.environ.get("AVITO_API_TIMEOUT_SECONDS", "10"))
AVITO_SYNC_DEBOUNCE_SECONDS = int(os.environ.get("AVITO_SYNC_DEBOUNCE_SECONDS", "3"))
YANDEX_MARKET_API_KEY = os.environ.get("YANDEX_MARKET_API_KEY", "")
YANDEX_MARKET_KEY_FILE = BASE_DIR / ".yandex-market-key"
YANDEX_MARKET_TIMEOUT = 20
YANDEX_MARKET_PUBLIC_URL = os.environ.get("YANDEX_MARKET_PUBLIC_URL", "").rstrip("/")
YANDEX_MARKET_TRUSTED_PROXIES = tuple(filter(None, os.environ.get("YANDEX_MARKET_TRUSTED_PROXIES", "").split(",")))
YANDEX_MARKET_WEBHOOK_NETWORKS = ("5.45.207.0/25", "141.8.142.0/25", "5.255.253.0/25")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
GOOGLE_SHEETS_DEFAULT_URL = os.environ.get(
    "GOOGLE_SHEETS_DEFAULT_URL",
    "https://docs.google.com/spreadsheets/d/1bNKeWmFyoWZOQDEuhCXxltv0YkK6ykW20tXI9uI2tiI/edit?usp=sharing",
)
GOOGLE_SHEETS_DEFAULT_TAB = os.environ.get("GOOGLE_SHEETS_DEFAULT_TAB", "Прайс CRM")
RAPIRA_MARKET_RATES_URL = "https://api.rapira.net/open/market/rates"
RAPIRA_API_TIMEOUT_SECONDS = 4
RAPIRA_RATES_CACHE_TTL_SECONDS = 15
COINBASE_EXCHANGE_RATES_URL = "https://api.coinbase.com/v2/exchange-rates"
COINBASE_API_TIMEOUT_SECONDS = 5
COINBASE_RATES_CACHE_TTL_SECONDS = 30
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

FILE_UPLOAD_PERMISSIONS = 0o600
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"business": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "filters": {"retail_tokens": {"()": "resource_storefront.log_filters.RetailTokenFilter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "business", "filters": ["retail_tokens"]}},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "gamebat.business": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"), "propagate": False}
    },
}
