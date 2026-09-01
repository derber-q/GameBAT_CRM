from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from .models import PermissionSetMetadata, User


class SuperuserOnlyAdminMixin:
    """Учётные записи и права нельзя менять обычными model permissions."""
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(User)
class GameBATUserAdmin(SuperuserOnlyAdminMixin, UserAdmin):
    list_display = ("username", "full_name", "email", "is_active", "is_superuser")
    search_fields = ("username", "full_name", "email", "phone_1")
    fieldsets = UserAdmin.fieldsets + (
        ("GameBAT", {"fields": ("full_name", "phone_1", "phone_2", "phone_3", "telegram", "verification_document")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("GameBAT", {"fields": ("full_name", "email", "phone_1", "phone_2", "phone_3", "telegram", "verification_document")}),
    )


@admin.register(PermissionSetMetadata)
class PermissionSetMetadataAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("group", "description")
    search_fields = ("group__name", "description")
    autocomplete_fields = ("group",)


admin.site.unregister(Group)


@admin.register(Group)
class GameBATGroupAdmin(SuperuserOnlyAdminMixin, GroupAdmin):
    pass
