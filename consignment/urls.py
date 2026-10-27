from django.urls import path
from . import views, report_views
from partners.platform_views import platform_create

app_name = "consignment"
urlpatterns = [
    path("platform/<int:pk>/report/", report_views.report_import, name="report_import"),
    path("sales/<int:pk>/partner-payment/", report_views.report_partner_payment, name="report_partner_payment"),
    path("", views.consignment_list, name="list"),
    path('platform/new/', platform_create, name='platform_create'),
    path("platform/<int:pk>/", views.consignment_platform, name="platform"),
    path("platform/<int:pk>/export/", views.platform_export, name="platform_export"),
    path("transfer/", views.transfer, name="transfer"),
    path("return/", views.return_stock, name="return"),
    path("stocks/<str:product_kind>/<int:pk>/reward/", views.reward_update, name="reward_update"),
    path("stocks/<str:product_kind>/<int:pk>/sold/", views.consignment_sale, name="sale"),
    path("stocks/<str:product_kind>/<int:pk>/action/", views.row_action, name="row_action"),
    path("movements/<int:pk>/", views.movement_detail, name="movement_detail"),
]
