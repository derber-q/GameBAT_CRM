from django.contrib import admin

from .models import (
    CDWarehouseStock,
    CDWarehouseTransferItem,
    TechWarehouseStock,
    TechWarehouseTransferItem,
    Warehouse,
    WarehouseTransfer,
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class CurrentStockAdmin(admin.ModelAdmin):
    """Текущие остатки меняются только через бизнес-операции CRM."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CDWarehouseStock)
class CDWarehouseStockAdmin(CurrentStockAdmin):
    list_display = ("warehouse", "cd", "quantity")
    list_filter = ("warehouse", "cd__platform")
    search_fields = ("cd__name", "cd__sku", "warehouse__name")


@admin.register(TechWarehouseStock)
class TechWarehouseStockAdmin(CurrentStockAdmin):
    list_display = ("warehouse", "tech", "quantity")
    list_filter = ("warehouse", "tech__product_type")
    search_fields = ("tech__name", "tech__sku", "warehouse__name")


class TransferHistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WarehouseTransfer)
class WarehouseTransferAdmin(TransferHistoryAdmin):
    list_display = ("id", "source_warehouse", "destination_warehouse", "status", "created_by", "created_at")
    list_filter = ("status", "source_warehouse", "destination_warehouse")
    search_fields = ("id", "created_by__username")
    date_hierarchy = "created_at"


@admin.register(CDWarehouseTransferItem)
class CDWarehouseTransferItemAdmin(TransferHistoryAdmin):
    list_display = ("transfer", "cd", "quantity")
    search_fields = ("cd__name", "cd__sku")


@admin.register(TechWarehouseTransferItem)
class TechWarehouseTransferItemAdmin(TransferHistoryAdmin):
    list_display = ("transfer", "tech", "quantity")
    search_fields = ("tech__name", "tech__sku")
