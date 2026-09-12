from django.urls import path

from . import views

app_name = "price"
urlpatterns = [
    path("", views.price_page, name="index"),
    path("settings/", views.document_settings_update, name="settings_update"),
    path("retail.xlsx", views.retail_export, name="retail_export"),
    path("wholesale.xlsx", views.wholesale_export, name="wholesale_export"),
    path("supplier-template.xlsx", views.supplier_template_export, name="supplier_template"),
    path("supplier/upload/", views.supplier_price_upload, name="supplier_upload"),
    path("procurement/create/", views.procurement_create, name="procurement_create"),
    path("procurement/<int:pk>/", views.procurement_detail, name="procurement_detail"),
    path("procurement/<int:pk>/update/", views.procurement_update, name="procurement_update"),
    path("procurement/<int:pk>/customer.xlsx", views.procurement_export, name="procurement_export"),
]
