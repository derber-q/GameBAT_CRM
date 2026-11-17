"""Настройки CI без рабочей БД, ключей и сетевых интеграций."""
import os

os.environ.update(GAMEBAT_ENV='local_live',DJANGO_SECRET_KEY='ci-only-not-a-production-secret',
    INTEGRATION_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=',
    RESOURCE_TOKEN_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=')
from GameBAT_CRM.settings import *  # noqa: F403

# Файловая тестовая SQLite повторяет блокировку записи рабочего SQLite.
# Shared-memory SQLite немедленно возвращает SQLITE_LOCKED вместо busy timeout
# при конкурентном inbox и не воспроизводит IMMEDIATE-транзакции приложения.
(BASE_DIR/'outputs').mkdir(parents=True, exist_ok=True)
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:',
    'OPTIONS':{'timeout':30,'transaction_mode':'IMMEDIATE'},
    'TEST':{'NAME':BASE_DIR/'outputs/ci_suite.sqlite3'}}}
UPDATE_STATUS_FILE=UPDATE_SOCKET=''
