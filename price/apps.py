"""Конфигурация приложения и его регистрация в Django прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом."""
from django.apps import AppConfig


class PriceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "price"
    verbose_name = "Прайс-листы"
