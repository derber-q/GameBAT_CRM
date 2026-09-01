from django.contrib import admin
from .models import SalesPlatform, Supplier


class SupplierDetailAdminMixin:
    """Не допускает раскрытия реквизитов через альтернативный интерфейс admin."""
    def _can_see_details(self, request):
        return request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")

    def has_module_permission(self, request):
        return self._can_see_details(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._can_see_details(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self._can_see_details(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._can_see_details(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._can_see_details(request) and super().has_delete_permission(request, obj)


@admin.register(Supplier)
class SupplierAdmin(SupplierDetailAdminMixin, admin.ModelAdmin):
    list_display = ("id", "letter", "name", "legal_entity", "phone_1", "email")
    search_fields = ("letter", "name", "legal_entity", "phone_1", "email")


@admin.register(SalesPlatform)
class SalesPlatformAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "address", "legal_entity", "phone_1", "email")
    search_fields = ("name", "address", "legal_entity", "phone_1")
