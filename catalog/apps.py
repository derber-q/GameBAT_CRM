"""Конфигурация приложения и его регистрация в Django номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry."""
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог и склад"
