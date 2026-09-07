from django.urls import path

from . import views

app_name = "warehouse"
urlpatterns = [
    path("global/", views.global_stock, name="global_stock"),
    path("transfers/", views.transfer_list, name="transfer_list"),
    path("transfers/new/", views.transfer_start, name="transfer_start"),
    path("transfers/<int:pk>/", views.transfer_detail, name="transfer_detail"),
    path("transfers/<int:pk>/advance/", views.transfer_advance, name="transfer_advance"),
    path("<int:source_pk>/transfers/new/", views.transfer_create, name="transfer_create"),
    path("<int:pk>/", views.warehouse_detail, name="detail"),
]
