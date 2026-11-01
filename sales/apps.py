"""Конфигурация приложения и его регистрация в Django продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки."""
from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sales"
    verbose_name = "Продажи"
