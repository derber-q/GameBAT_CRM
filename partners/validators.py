"""Валидаторы реквизитов контрагентов; клиентская маска не заменяет эти проверки."""
from django.core.validators import RegexValidator

hex_color_validator = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$",
    message="Укажите цвет в формате #RRGGBB.",
)
