"""Конфигурация приложения и его регистрация в Django реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются."""
from django.apps import AppConfig


class ConsignmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consignment"
    verbose_name = "Реализация"
