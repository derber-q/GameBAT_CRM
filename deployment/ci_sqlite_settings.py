"""Настройки CI без рабочей БД, ключей и сетевых интеграций."""
import os

os.environ.update(GAMEBAT_ENV='local_live',DJANGO_SECRET_KEY='ci-only-not-a-production-secret',
    INTEGRATION_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=',
    RESOURCE_TOKEN_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=')
from GameBAT_CRM.settings import *  # noqa: F403

DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:','TEST':{}}}
UPDATE_STATUS_FILE=UPDATE_SOCKET=''
