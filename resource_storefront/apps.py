"""Конфигурация приложения и его регистрация в Django оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении."""
from django.apps import AppConfig


class ResourceStorefrontConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "resource_storefront"
    verbose_name = "Оптовая витрина ReSOURCE"
