from django.contrib import admin

from .models import PriceDocumentSettings, ProcurementPriceList, ProcurementPriceListItem


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


@admin.register(PriceDocumentSettings)
class PriceDocumentSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not PriceDocumentSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


class ProcurementPriceListItemInline(admin.TabularInline):
    model = ProcurementPriceListItem
    extra = 0
    can_delete = False
    fields = (
        "product_kind", "product_name_snapshot", "article_snapshot", "selected_supplier",
        "supplier_price_aed", "exchange_rate_aed_rub", "base_price_rub", "markup_rub",
        "delivery_rub", "prepayment_price_rub", "postpayment_price_rub",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProcurementPriceList)
class ProcurementPriceListAdmin(admin.ModelAdmin):
    list_display = ("id", "exchange_rate_aed_rub", "created_by", "created_at")
    search_fields = ("public_token", "created_by__username", "created_by__full_name")
    readonly_fields = ("public_token", "exchange_rate_aed_rub", "created_by", "created_at")
    inlines = (ProcurementPriceListItemInline,)

    def get_inline_instances(self, request, obj=None):
        if not _can_view_supplier_snapshots(request):
            return []
        return super().get_inline_instances(request, obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcurementPriceListItem)
class ProcurementPriceListItemAdmin(SupplierSnapshotAdminMixin, admin.ModelAdmin):
    list_display = (
        "id", "price_list", "product_kind", "product_name_snapshot", "selected_supplier",
        "supplier_price_aed", "prepayment_price_rub", "postpayment_price_rub",
    )
    list_filter = ("product_kind", "selected_supplier")
    search_fields = ("product_name_snapshot", "article_snapshot")
    readonly_fields = [field.name for field in ProcurementPriceListItem._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
