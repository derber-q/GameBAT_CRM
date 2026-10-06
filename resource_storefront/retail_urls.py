from django.urls import path
from . import views, retail_views

app_name = "retailer"
urlpatterns = [
    path("", views.catalogue, name="home"),
    path("catalog/", views.catalogue, name="catalogue"),
    path("product/<str:kind>/<int:pk>/", views.product_detail, name="product"),
    path("product-photo/<str:kind>/<int:pk>/<int:image_id>/", views.product_photo, name="product_photo"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/update/<str:key>/", views.cart_update, name="cart_update"),
    path("cart/remove/<str:key>/", views.cart_remove, name="cart_remove"),
    path("cart/refresh/", views.cart_refresh, name="cart_refresh"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/status/", views.checkout_status, name="checkout_status"),
    path("order/<int:sale_id>/", views.order_success, name="success"),
    path("<str:token>/", retail_views.access, name="access"),
]
