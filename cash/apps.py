"""Конфигурация приложения и его регистрация в Django кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции."""
from django.apps import AppConfig


class CashConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cash"
    verbose_name = "Кассы"

    def ready(self):
        from . import signals  # noqa: F401
