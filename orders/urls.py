from django.urls import path

from . import views, trip_views, stock_order_views, trip_price_views, trip_invoice_views
from . import trip_addition_views, fulfillment_views, arrival_views

app_name = "orders"
urlpatterns = [
    path('trips/new/', trip_views.trip_empty_create, name='trip_empty_create'),
    path('trips/<int:pk>/orders/add/', trip_views.trip_add_orders, name='trip_add_orders'),
    path('trips/<int:pk>/arrival/',arrival_views.update_arrival,name='trip_arrival'),
    path('trips/<int:pk>/finalization/',arrival_views.finalization,name='arrival_finalization'),
    path('trips/<int:pk>/finalization/auto/',arrival_views.finalization_auto,name='arrival_finalization_auto'),
    path('trip-supplies/<int:pk>/post/',arrival_views.post_supply,name='arrival_supply_post'),
    path('<int:pk>/receipt/',arrival_views.receipt,name='arrival_receipt'),
    path('<int:pk>/operation/', fulfillment_views.prepare, name='operation_prepare'),
    path('trips/<int:pk>/additional/', trip_addition_views.addition, name='trip_addition'),
    path('trips/<int:pk>/additional/search/', trip_addition_views.product_search, name='trip_addition_search'),
    path('trips/<int:pk>/additional/calculation/', trip_addition_views.calculation, name='trip_addition_calculation'),
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
    path('trips/<int:pk>/suppliers/<int:supplier_pk>/invoice/', trip_invoice_views.invoice_update, name='trip_invoice_update'),
    path("trips/<int:pk>/export/", trip_views.trip_full_export, name="trip_full_export"),
    path("trips/<int:pk>/lines/<int:line_pk>/", trip_views.trip_line_update, name="trip_line_update"),
    path("trips/<int:pk>/lines/<int:line_pk>/price/preview/", trip_price_views.preview, name="trip_price_preview"),
    path("trips/<int:pk>/lines/<int:line_pk>/price/", trip_price_views.update, name="trip_price_update"),
    path("trips/<int:pk>/suppliers/<int:supplier_pk>/export/", trip_views.trip_export, name="trip_export"),
]
