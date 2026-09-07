from django.contrib import admin

from partners.admin import SupplierDetailAdminMixin
from .models import SupplierCDPrice, SupplierTechPrice


class SupplierPricePermissionMixin:
    def has_module_permission(self, request):
        allowed = request.user.is_superuser or request.user.has_perm("pricing.view_supplier_prices")
        return allowed and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        allowed = request.user.is_superuser or request.user.has_perm("pricing.view_supplier_prices")
        return allowed and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        allowed = request.user.is_superuser or request.user.has_perm("pricing.change_supplier_prices")
        return allowed and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        allowed = request.user.is_superuser or request.user.has_perm("pricing.change_supplier_prices")
        return allowed and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        allowed = request.user.is_superuser or request.user.has_perm("pricing.change_supplier_prices")
        return allowed and super().has_delete_permission(request, obj)


@admin.register(SupplierCDPrice)
class SupplierCDPriceAdmin(SupplierDetailAdminMixin, SupplierPricePermissionMixin, admin.ModelAdmin):
    list_display = ("supplier", "cd", "price", "updated_at")
    list_filter = ("supplier", "cd__platform")
    search_fields = ("cd__name", "cd__sku", "supplier__name")
    autocomplete_fields = ("supplier", "cd")
    readonly_fields = ("updated_at",)


@admin.register(SupplierTechPrice)
class SupplierTechPriceAdmin(SupplierDetailAdminMixin, SupplierPricePermissionMixin, admin.ModelAdmin):
    list_display = ("supplier", "tech", "price", "updated_at")
    list_filter = ("supplier", "tech__product_type")
    search_fields = ("tech__name", "tech__sku", "supplier__name")
    autocomplete_fields = ("supplier", "tech")
    readonly_fields = ("updated_at",)
