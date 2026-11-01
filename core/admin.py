"""Регистрация моделей и разрешённых действий в Django Admin общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев."""
from django.contrib import admin
from .models import CurrencyRate


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("pair", "rate", "updated_at")
    readonly_fields = ("updated_at",)
