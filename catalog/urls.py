"""Именованные HTTP-маршруты приложения номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry."""
from django.urls import path
from . import views

app_name = "catalog"
urlpatterns = [path("", views.warehouse, name="warehouse")]
