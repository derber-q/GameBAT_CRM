"""Только искусственный PostgreSQL CI, не конфигурация production."""
from .ci_sqlite_settings import *  # noqa: F403

DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':'resource_ci',
    'USER':'resource_ci','PASSWORD':'ci-only','HOST':'127.0.0.1','PORT':'5432','TEST':{'NAME':'test_resource_ci'}}}
