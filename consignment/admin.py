from django.contrib import admin
from .models import CDConsignmentStock, ConsignmentMovement, ConsignmentMovementItem, TechConsignmentStock


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
    list_display = ("platform", "warehouse", "cd", "quantity", "receivable_per_unit")
    list_filter = ("platform", "warehouse")
    search_fields = ("cd__name", "cd__sku", "platform__name", "warehouse__name")


@admin.register(TechConsignmentStock)
class TechConsignmentStockAdmin(CurrentStockAdmin):
    list_display = ("platform", "warehouse", "tech", "quantity", "receivable_per_unit")
    list_filter = ("platform", "warehouse")
    search_fields = ("tech__name", "tech__sku", "platform__name", "warehouse__name")


class ConsignmentMovementItemInline(admin.TabularInline):
    model = ConsignmentMovementItem
    extra = 0
    can_delete = False
    fields = (
        "product_kind", "product_name_snapshot", "product_sku_snapshot", "quantity",
        "receivable_per_unit", "warehouse_quantity_before", "warehouse_quantity_after",
        "consignment_quantity_before", "consignment_quantity_after",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ConsignmentMovement)
class ConsignmentMovementAdmin(CurrentStockAdmin):
    list_display = (
        "id", "operation_type", "position_count", "total_units", "platform", "warehouse",
        "created_by", "created_at",
    )
    list_filter = ("operation_type", "platform", "warehouse")
    search_fields = (
        "items__product_name_snapshot", "items__product_sku_snapshot",
        "created_by__username", "created_by__full_name",
    )
    readonly_fields = ("operation_type", "platform", "warehouse", "created_by", "created_at")
    inlines = (ConsignmentMovementItemInline,)


@admin.register(ConsignmentMovementItem)
class ConsignmentMovementItemAdmin(CurrentStockAdmin):
    list_display = (
        "movement", "product_kind", "product_name_snapshot", "quantity", "receivable_per_unit"
    )
    list_filter = ("product_kind", "movement__operation_type", "movement__platform")
    search_fields = ("product_name_snapshot", "product_sku_snapshot")
