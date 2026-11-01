"""Только искусственные SQLite и медиа для одноразовой проверки образа."""
from GameBAT_CRM.settings import *  # noqa: F403

DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':'/tmp/candidate.sqlite3'}}
MEDIA_ROOT = '/tmp/candidate-media'
GAMEBAT_ENV = 'local_test'
LABEL_PRINT_BACKEND = 'disabled'
UPDATE_STATE_DB = ''
