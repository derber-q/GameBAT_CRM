from django.contrib import admin
from django.urls import include, path
from core.admin_site import GameBATAdminAuthenticationForm


def gamebat_admin_permission(request):
    """Разрешает вход в admin только суперпользователю или по специальному праву."""
    user = request.user
    return bool(
        user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.has_perm("core.access_admin_panel"))
    )


admin.site.has_permission = gamebat_admin_permission
admin.site.login_form = GameBATAdminAuthenticationForm
admin.site.site_header = "GameBAT CRM — администрирование"
admin.site.site_title = "GameBAT CRM"
admin.site.index_title = "Управление данными"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("warehouse/", include("catalog.urls")),
    path("suppliers/", include("partners.urls")),
    path("supplies/", include("supplies.urls")),
    path("consignment/", include("consignment.urls")),
    path("", include("core.urls")),
]

handler403 = "core.views.permission_denied"
