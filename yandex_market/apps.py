from django.apps import AppConfig


class YandexMarketConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "yandex_market"
    verbose_name = "Яндекс Маркет"

    def ready(self):
        from . import signals  # noqa: F401
