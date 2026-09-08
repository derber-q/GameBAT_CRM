from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
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
admin.site.site_header = "ReSOURCE — администрирование"
admin.site.site_title = "ReSOURCE"
admin.site.index_title = "Управление данными"

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/img/gamebat-favicon.ico", permanent=True)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("warehouse/", include("catalog.urls")),
    path("warehouse/", include("warehouse.urls")),
    path("suppliers/", include("partners.urls")),
    path("supplies/", include("supplies.urls")),
    path("consignment/", include("consignment.urls")),
    path("pricing/", include("pricing.urls")),
    path("sales/", include("sales.urls")),
    path("cash/", include("cash.urls")),
    path("nomenclature/", include("catalog.nomenclature_urls")),
    path("", include("core.urls")),
]

handler403 = "core.views.permission_denied"
