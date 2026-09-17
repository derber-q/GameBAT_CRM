from django.contrib import admin
from .models import (
    Supply, SupplyCDItem, SupplyCostCalculation, SupplyExpense, SupplyFinalization,
    SupplyFinalizationItem, SupplyRevision, SupplyRevisionExpense, SupplyRevisionItem,
    SupplyTechItem,
)
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
    list_display = (
        "id", "accepted_at", "warehouse", "accepted_by", "total_units", "total_weight_grams",
        "expenses_total", "weight_transport_cost",
        "grand_total", "status", "cancelled_at", "cancelled_by",
        "revision_number", "last_revised_at", "last_revised_by",
    )
    list_filter = ("status", "warehouse", "accepted_at")
    search_fields = ("id", "accepted_by__username", "accepted_by__full_name")


@admin.register(SupplyCDItem)
class SupplyCDItemAdmin(SupplierDetailAdminMixin, HistoricalAdmin):
    list_display = (
        "supply", "product_name_snapshot", "quantity", "weight_grams_snapshot",
        "allocated_transport_cost", "purchase_unit_cost", "effective_unit_cost",
    )
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
    list_filter = ("supplier",)


@admin.register(SupplyTechItem)
class SupplyTechItemAdmin(SupplierDetailAdminMixin, HistoricalAdmin):
    list_display = (
        "supply", "product_name_snapshot", "quantity", "weight_grams_snapshot",
        "allocated_transport_cost", "purchase_unit_cost", "effective_unit_cost",
    )
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
    list_filter = ("supplier",)


@admin.register(SupplyExpense)
class SupplyExpenseAdmin(HistoricalAdmin):
    list_display = ("supply", "name", "amount")
    search_fields = ("name",)


@admin.register(SupplyCostCalculation)
class SupplyCostCalculationAdmin(HistoricalAdmin):
    list_display = (
        "supply", "product_name_snapshot", "old_owned_quantity", "incoming_quantity", "resulting_unit_cost"
    )
    list_filter = ("product_kind",)
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
    readonly_fields = (
        "supply", "product_kind", "cd", "tech", "product_name_snapshot", "product_sku_snapshot",
        "old_owned_quantity", "old_unit_cost", "old_inventory_value", "incoming_quantity",
        "incoming_value", "resulting_quantity", "resulting_value", "resulting_unit_cost",
    )


@admin.register(SupplyRevision)
class SupplyRevisionAdmin(HistoricalAdmin):
    list_display = ("supply", "revision_number", "created_at", "created_by", "warehouse", "reason")
    list_filter = ("warehouse", "created_at")
    search_fields = ("supply__id", "reason", "created_by__username", "created_by__full_name")


@admin.register(SupplyRevisionItem)
class SupplyRevisionItemAdmin(SupplierDetailAdminMixin, HistoricalAdmin):
    list_display = (
        "revision", "product_kind", "product_name_snapshot", "quantity",
        "purchase_unit_cost", "effective_unit_cost",
    )
    list_filter = ("product_kind", "supplier")
    search_fields = ("product_name_snapshot", "product_sku_snapshot")


@admin.register(SupplyRevisionExpense)
class SupplyRevisionExpenseAdmin(HistoricalAdmin):
    list_display = ("revision", "name", "amount")
    search_fields = ("name",)


@admin.register(SupplyFinalization)
class SupplyFinalizationAdmin(HistoricalAdmin):
    list_display = (
        "id", "supply", "created_at", "created_by", "supply_revision_number",
        "total_penalty_before_distribution", "status", "superseded_by_revision_number",
    )
    list_filter = ("status", "created_at")
    search_fields = ("supply__id", "created_by__username", "created_by__full_name")


@admin.register(SupplyFinalizationItem)
class SupplyFinalizationItemAdmin(HistoricalAdmin):
    list_display = (
        "finalization", "product_kind", "product_name_snapshot",
        "global_quantity_snapshot", "old_global_cost", "new_global_cost", "change_source",
    )
    list_filter = ("product_kind", "change_source")
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
