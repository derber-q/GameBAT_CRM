from django.contrib import admin
from .models import Supply, SupplyCDItem, SupplyExpense, SupplyTechItem
from partners.admin import SupplierDetailAdminMixin


class HistoricalAdmin(admin.ModelAdmin):
    """Принятые финансовые записи доступны в admin только для чтения."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Supply)
class SupplyAdmin(HistoricalAdmin):
    list_display = ("id", "accepted_at", "accepted_by", "total_units", "expenses_total", "grand_total", "status")
    list_filter = ("status", "accepted_at")
    search_fields = ("id", "accepted_by__username", "accepted_by__full_name")


@admin.register(SupplyCDItem)
class SupplyCDItemAdmin(SupplierDetailAdminMixin, HistoricalAdmin):
    list_display = ("supply", "product_name_snapshot", "quantity", "purchase_unit_cost", "effective_unit_cost")
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
    list_filter = ("supplier",)


@admin.register(SupplyTechItem)
class SupplyTechItemAdmin(SupplierDetailAdminMixin, HistoricalAdmin):
    list_display = ("supply", "product_name_snapshot", "quantity", "purchase_unit_cost", "effective_unit_cost")
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
    list_filter = ("supplier",)


@admin.register(SupplyExpense)
class SupplyExpenseAdmin(HistoricalAdmin):
    list_display = ("supply", "name", "amount")
    search_fields = ("name",)
