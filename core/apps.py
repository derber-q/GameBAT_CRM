"""Конфигурация приложения и его регистрация в Django общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Общее"
