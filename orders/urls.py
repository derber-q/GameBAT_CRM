from django.urls import path

from . import views

app_name = "orders"
urlpatterns = [
    path("", views.order_list, name="list"),
    path("new/", views.order_upload, name="upload"),
    path("new/preview/", views.order_preview, name="preview"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/edit/", views.order_edit, name="edit"),
    path("<int:pk>/confirm/", views.order_confirm, name="confirm"),
    path("<int:pk>/receiving/", views.order_start_receiving, name="start_receiving"),
    path("<int:pk>/adjust/", views.order_adjust, name="adjust"),
    path("<int:pk>/complete/", views.order_complete, name="complete"),
    path("supplier-batches/create/", views.supplier_batch_create, name="supplier_batch_create"),
    path("supplier-batches/<int:pk>/", views.supplier_batch_detail, name="supplier_batch_detail"),
]
