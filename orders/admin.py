from django.contrib import admin

from .models import (
    CustomerOrderStatusEvent,
    CustomerProcurementOrder,
    CustomerProcurementOrderItem,
    OrderAdjustment,
    OrderAdjustmentChange,
    SupplierOrderBatch,
    SupplierOrderBatchLine,
)


def _can_view_supplier_snapshots(request):
    return request.user.is_superuser or (
        request.user.has_perm("price.view_supplier_prices")
        and request.user.has_perm("partners.view_supplier_details")
    )


class SupplierSnapshotAdminMixin:
    def has_module_permission(self, request):
        return _can_view_supplier_snapshots(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return _can_view_supplier_snapshots(request) and super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return _can_view_supplier_snapshots(request) and super().has_change_permission(request, obj)


class ReadonlyHistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm("orders.view_order_detail")

    def has_delete_permission(self, request, obj=None):
        return False


class OrderItemInline(admin.TabularInline):
    model = CustomerProcurementOrderItem
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in CustomerProcurementOrderItem._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CustomerProcurementOrder)
class CustomerProcurementOrderAdmin(ReadonlyHistoryAdmin):
    list_display = (
        "id", "recipient", "status", "payment_warehouse", "prepayment_total",
        "postpayment_total", "grand_total", "created_by", "created_at",
    )
    list_filter = ("status", "payment_warehouse", "created_at")
    search_fields = ("recipient", "comment", "created_by__username", "created_by__full_name")
    readonly_fields = [field.name for field in CustomerProcurementOrder._meta.fields]
    inlines = (OrderItemInline,)

    def get_inline_instances(self, request, obj=None):
        if not _can_view_supplier_snapshots(request):
            return []
        return super().get_inline_instances(request, obj)


@admin.register(CustomerProcurementOrderItem)
class CustomerProcurementOrderItemAdmin(SupplierSnapshotAdminMixin, ReadonlyHistoryAdmin):
    list_display = (
        "order", "product_name_snapshot", "selected_supplier",
        "prepayment_quantity", "postpayment_quantity",
    )
    search_fields = ("product_name_snapshot", "article_snapshot", "order__recipient")
    readonly_fields = [field.name for field in CustomerProcurementOrderItem._meta.fields]


@admin.register(CustomerOrderStatusEvent)
class CustomerOrderStatusEventAdmin(ReadonlyHistoryAdmin):
    list_display = ("order", "old_status", "new_status", "actor", "created_at")
    readonly_fields = [field.name for field in CustomerOrderStatusEvent._meta.fields]


class AdjustmentChangeInline(admin.TabularInline):
    model = OrderAdjustmentChange
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in OrderAdjustmentChange._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OrderAdjustment)
class OrderAdjustmentAdmin(ReadonlyHistoryAdmin):
    list_display = ("order", "actor", "refund_amount", "created_at")
    readonly_fields = [field.name for field in OrderAdjustment._meta.fields]
    inlines = (AdjustmentChangeInline,)


@admin.register(OrderAdjustmentChange)
class OrderAdjustmentChangeAdmin(ReadonlyHistoryAdmin):
    list_display = ("adjustment", "product_name_snapshot", "field_name", "old_value", "new_value")
    readonly_fields = [field.name for field in OrderAdjustmentChange._meta.fields]


class BatchLineInline(admin.TabularInline):
    model = SupplierOrderBatchLine
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in SupplierOrderBatchLine._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupplierOrderBatch)
class SupplierOrderBatchAdmin(SupplierSnapshotAdminMixin, ReadonlyHistoryAdmin):
    list_display = ("id", "created_by", "created_at")
    readonly_fields = ("created_by", "created_at", "source_orders")
    inlines = (BatchLineInline,)


@admin.register(SupplierOrderBatchLine)
class SupplierOrderBatchLineAdmin(SupplierSnapshotAdminMixin, ReadonlyHistoryAdmin):
    list_display = ("batch", "supplier", "product_name_snapshot", "quantity")
    list_filter = ("supplier", "product_kind")
    readonly_fields = [field.name for field in SupplierOrderBatchLine._meta.fields]
