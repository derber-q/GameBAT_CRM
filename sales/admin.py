from django.contrib import admin

from .models import Sale, SaleCDItem, SaleTechItem


class SaleHistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(SaleHistoryAdmin):
    list_display = (
        "visible_id", "warehouse", "consignment_platform", "sale_type", "payment_method", "order_status",
        "payment_status", "total_amount", "refunded_amount", "cancelled_at", "cancelled_by", "created_at",
    )
    list_filter = (
        "warehouse", "consignment_platform", "sale_type", "payment_method", "order_status", "payment_status",
        "cancelled_at",
    )
    search_fields = ("visible_id", "created_by__username", "created_by__full_name")
    date_hierarchy = "created_at"


@admin.register(SaleCDItem)
class SaleCDItemAdmin(SaleHistoryAdmin):
    list_display = ("sale", "product_name_snapshot", "quantity", "unit_price", "line_total")
    search_fields = ("sale__visible_id", "product_name_snapshot", "article_snapshot")


@admin.register(SaleTechItem)
class SaleTechItemAdmin(SaleHistoryAdmin):
    list_display = ("sale", "product_name_snapshot", "quantity", "unit_price", "line_total")
    search_fields = ("sale__visible_id", "product_name_snapshot", "article_snapshot")
