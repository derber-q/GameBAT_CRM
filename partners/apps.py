"""Конфигурация приложения и его регистрация в Django контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь."""
from django.apps import AppConfig


class PartnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "partners"
    verbose_name = "Партнёры"
