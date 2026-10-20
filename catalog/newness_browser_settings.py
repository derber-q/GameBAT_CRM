"""Отдельная SQLite только для явного запуска браузерных проверок карточек."""
from GameBAT_CRM.settings import *  # noqa: F403

DATABASES = {'default': {
    **DATABASES['default'],
    'TEST': {'NAME': BASE_DIR / 'outputs' / 'catalog_features_20261020' / 'browser-test.sqlite3'},
}}
