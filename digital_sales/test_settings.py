"""Отдельная SQLite для параллельной профильной проверки, не рабочая CRM."""
from GameBAT_CRM.settings import *  # noqa: F403

DATABASES = {'default': {**DATABASES['default'], 'TEST': {'NAME': BASE_DIR / 'outputs/digital-isolated-tests.sqlite3'}}}  # noqa: F405
