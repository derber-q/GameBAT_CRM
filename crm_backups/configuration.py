"""Явный allowlist эффективных ключей и файлов. Не читает секреты в local_test."""
import base64
import os
from pathlib import Path
import subprocess
from django.conf import settings
from django.apps import apps
from django.db import models
from core.external_policy import require_live_operation
from deployment.version import current_version


def sqlite_worker_lock(database):
    """Привязка к БД, а не каталогу архивов: два разных cache root не создают
    двух исполнителей для одной SQLite и не отменяют чужой активный снимок.
    """
    path=Path(database).resolve()
    if not path.is_file():raise ValueError('Рабочая SQLite для исполнителя отсутствует.')
    return path.with_name('.'+path.name+'.backup-worker.lock')


def backup_root():
    require_live_operation('backup_storage')
    root = Path(getattr(settings, 'CRM_BACKUP_ROOT', settings.BASE_DIR / '.local-backup-cache'))
    if root.resolve()!=root.absolute() or root.is_symlink() or root.is_junction() or root.resolve().is_relative_to(Path(settings.MEDIA_ROOT).resolve()):
        raise ValueError('Небезопасный каталог серверных архивов.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name=='nt':
        from local_agent.configuration import private_folder
        private_folder(root)
    return root


def recovery_secrets():
    require_live_operation('backup_secrets')
    result = {name: str(getattr(settings, name, '') or '') for name in (
        'SECRET_KEY', 'INTEGRATION_ENCRYPTION_KEY', 'RESOURCE_TOKEN_ENCRYPTION_KEY',
        'YANDEX_MARKET_API_KEY')}
    result['TELEGRAM_STAFF_BOT_TOKEN'] = os.environ.get('GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN', '')
    if not result['INTEGRATION_ENCRYPTION_KEY']:
        path = Path(settings.INTEGRATION_ENCRYPTION_KEY_FILE)
        if path.is_file(): result['INTEGRATION_ENCRYPTION_KEY'] = path.read_text('ascii').strip()
    files = {}
    paths = {
        'yandex-market-key': getattr(settings, 'YANDEX_MARKET_KEY_FILE', ''),
        'google-service-account.json': getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', ''),
        'telegram-staff-bot-token': getattr(settings, 'TELEGRAM_STAFF_TOKEN_FILE', settings.BASE_DIR / '.telegram-staff-bot-token'),
        'label-printer.json': getattr(settings,'LABEL_PRINTER_CONFIG_PATH',settings.BASE_DIR / '.label-printer.json'),
    }
    for name, value in paths.items():
        if not value: continue
        path = Path(value)
        if path.is_symlink() or path.is_junction(): raise ValueError('Ссылка вместо файла конфигурации.')
        if path.is_file():
            if path.stat().st_size > 1024 * 1024: raise ValueError('Файл секрета слишком большой.')
            files[name] = base64.b64encode(path.read_bytes()).decode()
        elif name=='google-service-account.json':
            raise ValueError('Настроенный ключ Google отсутствует; полная копия невозможна.')
    result['files_base64'] = files
    return result


def columns():
    file_columns = []
    encrypted = []
    for model in apps.get_models():
        for field in model._meta.local_fields:
            if isinstance(field, models.FileField):
                file_columns.append((model._meta.db_table, field.column))
            if field.name.startswith('encrypted_'):
                key = 'RESOURCE_TOKEN_ENCRYPTION_KEY' if model._meta.app_label == 'resource_storefront' else 'INTEGRATION_ENCRYPTION_KEY'
                encrypted.append((model._meta.db_table, field.column, key))
    return file_columns, encrypted


def version_metadata():
    version = current_version(settings.BASE_DIR)
    # Git status не раскрывает содержимое файлов; отсутствие Git — неизвестно, не clean.
    dirty = None
    try:
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=settings.BASE_DIR,
            timeout=5, stderr=subprocess.DEVNULL))
    except (OSError, subprocess.SubprocessError): pass
    return {**version, 'dirty': dirty, 'reproducible': dirty is False,
            'environment': settings.GAMEBAT_ENV, 'database_engine': 'sqlite'}
