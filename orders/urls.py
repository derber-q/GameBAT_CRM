from django.urls import path

from . import views, trip_views, stock_order_views

app_name = "orders"
urlpatterns = [
    path("", views.order_list, name="list"),
    path("new/", views.order_upload, name="upload"),
    path("new/stock/", stock_order_views.stock_order_create, name="stock_create"),
    path("new/preview/", views.order_preview, name="preview"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/export/", views.order_export, name="export"),
    path("<int:pk>/export/suppliers/", views.order_suppliers_export, name="export_suppliers"),
    path("<int:pk>/edit/", views.order_edit, name="edit"),
    path("<int:pk>/trip/", trip_views.order_trip_assign, name="assign_trip"),
    path("<int:pk>/confirm/", views.order_confirm, name="confirm"),
    path("<int:pk>/receiving/", views.order_start_receiving, name="start_receiving"),
    path("<int:pk>/adjust/", views.order_adjust, name="adjust"),
    path("<int:pk>/complete/", views.order_complete, name="complete"),
    path("supplier-batches/create/", views.supplier_batch_create, name="supplier_batch_create"),
    path("supplier-batches/<int:pk>/", views.supplier_batch_detail, name="supplier_batch_detail"),
    path("trips/create/", trip_views.trip_create, name="trip_create"),
    path("trips/<int:pk>/", trip_views.trip_detail, name="trip_detail"),
    path("trips/<int:pk>/export/", trip_views.trip_full_export, name="trip_full_export"),
    path("trips/<int:pk>/lines/<int:line_pk>/", trip_views.trip_line_update, name="trip_line_update"),
    path("trips/<int:pk>/suppliers/<int:supplier_pk>/export/", trip_views.trip_export, name="trip_export"),
]
