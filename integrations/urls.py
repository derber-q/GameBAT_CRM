from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("", views.api_keys, name="api_keys"),
    path("credentials/save/", views.credentials_save, name="credentials_save"),
    path("credentials/check/", views.credentials_check, name="credentials_check"),
    path("avito/", views.avito_dashboard, name="avito"),
    path("avito/sync/", views.manual_sync, name="manual_sync"),
    path("avito/sync/<int:pk>/status/", views.manual_sync_status, name="manual_sync_status"),
    path("avito/connections/", views.connections, name="connections"),
    path("avito/connections/refresh/", views.listings_refresh, name="listings_refresh"),
    path("avito/listings/<int:pk>/bind/", views.listing_bind, name="bind"),
    path("avito/connections/<int:pk>/rebind/", views.listing_rebind, name="rebind"),
    path("avito/connections/<int:pk>/unbind/", views.listing_unbind, name="unbind"),
    path("avito/products/<str:product_kind>/<int:pk>/", views.product_profile_save, name="product_save"),
    path("avito/products/<str:product_kind>/<int:pk>/photos/", views.product_photo_add, name="photo_add"),
    path("avito/products/<str:product_kind>/<int:pk>/photos/<int:photo_id>/delete/", views.product_photo_delete, name="photo_delete"),
    path("avito/products/<str:product_kind>/<int:pk>/photos/<int:photo_id>/move/", views.product_photo_move, name="photo_move"),
]
