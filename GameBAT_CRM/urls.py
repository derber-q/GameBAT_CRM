from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import include, path
from django.views.decorators.http import require_GET
from django.conf import settings
from django.conf.urls.static import static

from core.admin_site import GameBATAdminAuthenticationForm
from yandex_market.webhooks import notification as yandex_notification
from yandex_market.views import public_media as yandex_public_media


def gamebat_admin_permission(request):
    user = request.user
    return bool(user.is_authenticated and user.is_active and (user.is_superuser or user.has_perm("core.access_admin_panel")))


admin.site.has_permission = gamebat_admin_permission
admin.site.login_form = GameBATAdminAuthenticationForm
admin.site.site_header = "ReSOURCE — администрирование"
admin.site.site_title = "ReSOURCE"
admin.site.index_title = "Управление данными"


@require_GET
def crm_entry(request):
    return HttpResponseRedirect("/crm/accounts/login/")


urlpatterns = [
    path("", crm_entry, name="root"),
    # Existing marketplace notification URL is externally configured and stays stable.
    path("integrations/yandex/notifications/", yandex_notification, name="yandex_market_public_notification"),
    path("integrations/yandex/media/<uuid:public_id>/", yandex_public_media, name="yandex_market_public_media"),
    path("crm/admin/", admin.site.urls),
    path("crm/accounts/", include("accounts.urls")),
    path("crm/warehouse/", include("catalog.urls")),
    path("crm/warehouse/", include("warehouse.urls")),
    path("crm/suppliers/", include("partners.urls")),
    path("crm/supplies/", include("supplies.urls")),
    path("crm/consignment/", include("consignment.urls")),
    path("crm/pricing/", include("pricing.urls")),
    path("crm/price/", include("price.urls")),
    path("crm/sales/", include("sales.urls")),
    path("crm/statistics/", include("sales.statistics_urls")),
    path("crm/orders/", include("orders.urls")),
    path("crm/cash/", include("cash.urls")),
    path("crm/creditors/", include("creditors.urls")),
    path("crm/nomenclature/", include("catalog.nomenclature_urls")),
    path("crm/integrations/yandex/", include("yandex_market.urls")),
    path("crm/integrations/", include("integrations.urls")),
    path("crm/", include("core.urls")),
    path("", include("resource_storefront.urls")),
    path("retailer/", include("resource_storefront.retail_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler403 = "core.views.permission_denied"
