from django.urls import path

from . import views, fbs_views
from . import avito_check_views

app_name = "pricing"
urlpatterns = [
    path("", views.pricing_list, name="list"),
    path("fbs/<str:kind>/<int:pk>/", fbs_views.detail, name="fbs_detail"),
    path("fbs/<str:kind>/<int:pk>/preview/", fbs_views.preview, name="fbs_preview"),
    path("fbs/<str:kind>/<int:pk>/save/", fbs_views.save, name="fbs_save"),
    path("avito-check/", avito_check_views.page, name="avito_check"),
    path("avito-check/automatic/", avito_check_views.automatic_page, name="avito_check_automatic"),
    path("avito-check/found-price/", avito_check_views.save_found_price, name="avito_check_found_price"),
    path("avito-check/next/", avito_check_views.next_product, name="avito_check_next"),
    path("avito-check/check/", avito_check_views.check_product, name="avito_check_run"),
    path("product/update/", views.product_prices_update, name="product_update"),
    path("supplier/update/", views.supplier_price_update, name="supplier_update"),
]
