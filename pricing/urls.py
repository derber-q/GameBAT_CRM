from django.urls import path

from . import views

app_name = "pricing"
urlpatterns = [
    path("", views.pricing_list, name="list"),
    path("product/update/", views.product_prices_update, name="product_update"),
    path("supplier/update/", views.supplier_price_update, name="supplier_update"),
]
