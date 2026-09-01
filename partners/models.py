from django.db import models
from .validators import hex_color_validator


class Supplier(models.Model):
    name = models.CharField("Название", max_length=255)
    letter = models.CharField("Буква", max_length=8, unique=True)
    highlight_color = models.CharField("Цвет", max_length=7, validators=[hex_color_validator])
    legal_entity = models.CharField("Юридическое лицо", max_length=255)
    email = models.EmailField("Email", blank=True)
    phone_1 = models.CharField("Телефон №1", max_length=40)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    phone_3 = models.CharField("Телефон №3", max_length=40, blank=True)
    website = models.URLField("Сайт", blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)

    class Meta:
        ordering = ("letter",)
        verbose_name = "поставщик"
        verbose_name_plural = "поставщики"
        permissions = [("view_supplier_details", "Может видеть полные данные поставщиков")]

    def __str__(self):
        return self.name

    @property
    def safe_label(self):
        return f"[{self.letter}]"


class SalesPlatform(models.Model):
    name = models.CharField("Название", max_length=255)
    address = models.CharField("Адрес", max_length=500)
    legal_entity = models.CharField("Юридическое лицо", max_length=255)
    phone_1 = models.CharField("Телефон №1", max_length=40)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    phone_3 = models.CharField("Телефон №3", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "площадка реализации"
        verbose_name_plural = "площадки реализации"

    def __str__(self):
        return self.name
