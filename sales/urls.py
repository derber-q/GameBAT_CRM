from django.urls import path

from . import views
from . import market_views

app_name = "sales"
urlpatterns = [
    path("", views.sale_list, name="list"),
    path("incomplete/", views.sale_list, name="incomplete"),
    path("completed/", views.sale_completed_list, name="completed"),
    path("cancelled/", views.sale_cancelled_list, name="cancelled"),
    path("<int:pk>/status/", views.sale_inline_status, name="inline_status"),
    path('<int:pk>/market-action/', market_views.sale_market_action, name='market_action'),
    path('market-scan/', market_views.sale_market_scan, name='market_scan'),
    path('<int:pk>/market-print/', market_views.sale_market_print, name='market_print'),
    path('market-print/<uuid:request_id>/', market_views.sale_market_print_status, name='market_print_status'),
    path('<int:pk>/market-label/', market_views.sale_market_label, name='market_label'),
    path('<int:pk>/market-label/<int:document_id>/', market_views.sale_market_label_status, name='market_label_status'),
    path("new/", views.sale_create, name="create"),
    path("new/import-wholesale/", views.sale_wholesale_import, name="import_wholesale"),
    path("<int:pk>/", views.sale_detail, name="detail"),
    path("<int:pk>/invoice/", views.sale_invoice, name="invoice"),
    path("<int:pk>/edit/", views.sale_edit, name="edit"),
    path("<int:pk>/advance/", views.sale_advance, name="advance"),
    path("<int:pk>/payment-method/", views.sale_payment_method, name="payment_method"),
    path("<int:pk>/mark-paid/", views.sale_mark_paid, name="mark_paid"),
    path("<int:pk>/note/", views.sale_note_update, name="note_update"),
    path("<int:pk>/cancel/", views.sale_cancel, name="cancel"),
]
