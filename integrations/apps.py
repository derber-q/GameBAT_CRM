"""Конфигурация приложения и его регистрация в Django Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker."""
from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
    verbose_name = "Интеграции"

    def ready(self):
        from . import signals  # noqa: F401
