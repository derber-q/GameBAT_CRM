"""Настройки только для явного запуска изолированных браузерных проверок."""
from GameBAT_CRM.settings import *  # noqa: F403

DATABASES = {"default": {
    **DATABASES["default"],
    "TEST": {"NAME": BASE_DIR / "outputs" / "system-products-browser-test.sqlite3"},
}}
