"""Конфигурация приложения и его регистрация в Django пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Пользователи"
