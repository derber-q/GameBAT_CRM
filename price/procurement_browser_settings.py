"""Отдельная SQLite для явного запуска браузерных проверок закупочного прайса."""
from GameBAT_CRM.settings import *  # noqa: F403

DATABASES = {'default': {
    **DATABASES['default'],
    'TEST': {'NAME': BASE_DIR / 'outputs' / 'procurement-suppliers-browser.sqlite3'},
}}
