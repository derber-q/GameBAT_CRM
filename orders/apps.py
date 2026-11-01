"""Конфигурация приложения и его регистрация в Django импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно."""
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"
    verbose_name = "Заказы"

    def ready(self):
        from . import signals  # noqa: F401
