"""Только для явного запуска браузерных тестов; рабочая БД не подменяется тестовой."""
from GameBAT_CRM.settings import *  # noqa: F403

# Общая in-memory SQLite-связь ненадёжна при параллельных запросах LiveServer.
# TEST.NAME используется исключительно Django test runner.
DATABASES = {"default": {
    **DATABASES["default"],
    "TEST": {"NAME": BASE_DIR / "outputs" / "mobile-browser-test.sqlite3"},
    "OPTIONS": {**DATABASES["default"].get("OPTIONS", {}), "timeout": 30},
}}
