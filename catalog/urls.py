"""Именованные HTTP-маршруты приложения номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry."""
from django.urls import path
from . import views

app_name = "catalog"
urlpatterns = [
    path('barcode/lookup/', views.barcode_lookup, name='barcode_lookup'),
    path("", views.warehouse, name="warehouse"),
]
