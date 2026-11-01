"""Режим определяется до загрузки БД/ключей. local_live сохраняет прежние настройки."""
import json
import os
from pathlib import Path
import uuid

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

MODES = ('local_live', 'local_test', 'production')
SECRET_VARIABLES = (
    'DJANGO_SECRET_KEY', 'INTEGRATION_ENCRYPTION_KEY', 'INTEGRATION_ENCRYPTION_KEY_FILE',
    'RESOURCE_TOKEN_ENCRYPTION_KEY', 'RESOURCE_TOKEN_ENCRYPTION_KEY_FILE',
    'GOOGLE_SERVICE_ACCOUNT_FILE', 'YANDEX_MARKET_API_KEY', 'YANDEX_MARKET_KEY_FILE',
    'DATABASE_URL', 'DATABASE_NAME', 'DATABASE_HOST', 'DATABASE_PASSWORD',
    'GAMEBAT_DATABASE_PATH', 'GAMEBAT_MEDIA_ROOT', 'LABEL_PRINTER_CONFIG_PATH',
)


def selected_mode():
    mode = os.environ.get('GAMEBAT_ENV', 'local_live')
    if mode not in MODES:
        raise ImproperlyConfigured('GAMEBAT_ENV: допустимы local_live, local_test, production.')
    if mode == 'production':
        # Этап B ещё не прошёл проверку PostgreSQL и Linux. Не позволяем незаметно
        # открыть рабочую SQLite или сгенерировать новые ключи для production.
        raise ImproperlyConfigured('production заблокирован до проверки этапа B: PostgreSQL, явные секреты и Linux-запуск.')
    return mode


def test_root(base_dir):
    allowed = base_dir / 'outputs' / 'local_test'
    raw = Path(os.environ.get('GAMEBAT_TEST_ROOT', allowed / 'default')).absolute()
    resolved = raw.resolve()
    if resolved != raw or not resolved.is_relative_to(allowed.absolute()) or resolved == allowed.absolute():
        raise ImproperlyConfigured('GAMEBAT_TEST_ROOT должен быть отдельным каталогом внутри outputs/local_test, без символьных ссылок.')
    # Даже неполная конфигурация живого окружения не должна silently попасть в тест.
    if any(os.environ.get(key) for key in SECRET_VARIABLES):
        raise ImproperlyConfigured('local_test: обнаружена конфигурация другого окружения. Используйте отдельный тестовый запуск.')
    root = resolved
    root.mkdir(parents=True, exist_ok=True)
    marker = root / 'environment.json'
    if marker.resolve() != marker or marker.is_symlink():
        raise ImproperlyConfigured('local_test: ссылка вместо метки окружения запрещена.')
    if marker.exists():
        try:
            data = json.loads(marker.read_text('utf-8'))
            uuid.UUID(data['instance'])
            if data['mode'] != 'local_test':
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise ImproperlyConfigured('local_test: недопустимая метка каталога данных.') from None
    else:
        if any(root.iterdir()):
            raise ImproperlyConfigured('local_test: каталог без метки должен быть пустым; импорт рабочей БД запрещён.')
        data = {'mode':'local_test', 'instance':str(uuid.uuid4())}
        with marker.open('x', encoding='utf-8') as stream:
            json.dump(data, stream)
    for name in ('secrets', 'media', 'tmp', 'logs', 'workers'):
        path = root / name
        if path.resolve() != path or path.is_symlink():
            raise ImproperlyConfigured('local_test: перенаправление каталога данных запрещено.')
        path.mkdir(exist_ok=True)
    for name, factory in (('django.key',get_random_secret_key), ('integrations.key', lambda:Fernet.generate_key().decode()),
                          ('storefront.key',lambda:Fernet.generate_key().decode())):
        path = root / 'secrets' / name
        if path.resolve() != path or path.is_symlink() or (path.exists() and path.stat().st_nlink > 1):
            raise ImproperlyConfigured('local_test: ссылка вместо ключа запрещена.')
        try:
            with path.open('x', encoding='utf-8') as stream:
                stream.write(factory())
        except FileExistsError:
            pass
    return root, data['instance']


def apply_test_settings(values, base_dir):
    root, instance = test_root(base_dir)
    from .test_guard import install
    install(base_dir, root)
    import tempfile
    tempfile.tempdir = str(root / 'tmp')
    values.update(
        GAMEBAT_DATA_ROOT=root, GAMEBAT_INSTANCE=instance,
        SECRET_KEY=(root/'secrets/django.key').read_text('utf-8'),
        DEBUG=False, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
        ALLOWED_HOSTS=['localhost','127.0.0.1','[::1]','testserver'],
        SESSION_COOKIE_NAME='resource_test_session_'+instance[:8], CSRF_COOKIE_NAME='resource_test_csrf_'+instance[:8],
        SESSION_COOKIE_DOMAIN=None, CSRF_COOKIE_DOMAIN=None,
        MEDIA_ROOT=root/'media', STATIC_ROOT=root/'static', FILE_UPLOAD_TEMP_DIR=str(root/'tmp'),
        INTEGRATION_ENCRYPTION_KEY='', INTEGRATION_ENCRYPTION_KEY_FILE=root/'secrets/integrations.key',
        RESOURCE_TOKEN_ENCRYPTION_KEY=(root/'secrets/storefront.key').read_text('utf-8'),
        YANDEX_MARKET_API_KEY='', YANDEX_MARKET_KEY_FILE=root/'secrets/yandex.key',
        GOOGLE_SERVICE_ACCOUNT_FILE='', GOOGLE_SHEETS_DEFAULT_URL='', GOOGLE_SHEETS_DEFAULT_TAB='Тест',
        LABEL_PRINTER_CONFIG_PATH=root/'secrets/printer.json', YANDEX_MARKET_PUBLIC_URL='',
        LABEL_PRINT_BACKEND='disabled',
        YANDEX_MARKET_TRUSTED_PROXIES=(), YANDEX_MARKET_WEBHOOK_NETWORKS=(),
        WORKER_RUNTIME_DIR=root/'workers',
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
        CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache',
                            'LOCATION':'resource-local-test-'+instance}},
    )
    values['DATABASES']={'default':{
        'ENGINE':'django.db.backends.sqlite3', 'NAME':root/'test.sqlite3',
        'OPTIONS':values['DATABASES']['default']['OPTIONS'].copy(),
        'TEST':{'NAME':root/'suite.sqlite3'},
    }}
    values['TEMPLATES'][0]['OPTIONS']['context_processors'].append('core.environment_context.environment')
    values['MIDDLEWARE'].insert(0, 'core.environment_context.TestEnvironmentMiddleware')
