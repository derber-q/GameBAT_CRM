from django.contrib import admin
from .models import CDConsignmentStock, TechConsignmentStock


class CurrentStockAdmin(admin.ModelAdmin):
    """Остатки меняются только атомарными операциями рабочего интерфейса."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CDConsignmentStock)
class CDConsignmentStockAdmin(CurrentStockAdmin):
    list_display = ("platform", "cd", "quantity", "reward_per_unit")
    list_filter = ("platform",)
    search_fields = ("cd__name", "cd__sku", "platform__name")
    autocomplete_fields = ("platform", "cd")


@admin.register(TechConsignmentStock)
class TechConsignmentStockAdmin(CurrentStockAdmin):
    list_display = ("platform", "tech", "quantity", "reward_per_unit")
    list_filter = ("platform",)
    search_fields = ("tech__name", "tech__sku", "platform__name")
    autocomplete_fields = ("platform", "tech")
