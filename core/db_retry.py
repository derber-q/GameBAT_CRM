"""Повтор целой атомарной операции при кратком конфликте записи SQLite."""
from functools import wraps
import time
from django.db import connection, OperationalError


def retry_database_lock(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        attempts = 4 if connection.vendor == 'sqlite' and not connection.in_atomic_block else 1
        for attempt in range(attempts):
            try:
                return function(*args, **kwargs)
            except OperationalError as exc:
                if 'locked' not in str(exc).lower() or attempt == attempts - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))
    return wrapped
