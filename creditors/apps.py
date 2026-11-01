"""Конфигурация приложения и его регистрация в Django задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны."""
from django.apps import AppConfig


class CreditorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "creditors"
    verbose_name = "Кредиторы"
