"""Конфигурация приложения и его регистрация в Django приходов.

Проведение меняет остаток/оценку через сервис; предварительная проверка цен товар не приходует."""
from django.apps import AppConfig


class SuppliesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "supplies"
    verbose_name = "Поставки"
