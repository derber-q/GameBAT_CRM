"""Конфигурация приложения и его регистрация в Django складов.

Различать физический остаток конкретного склада, реализацию и товар в пути."""
from django.apps import AppConfig


class WarehouseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "warehouse"
    verbose_name = "Склады и перемещения"

    def ready(self):
        from . import signals  # noqa: F401
