"""Именованные HTTP-маршруты приложения общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев."""
from django.urls import path
from . import views
from .update_health import update_health

app_name = "core"
urlpatterns = [
    path('update-health/', update_health, name='update_health'),
    path("api/exchange-rates/", views.exchange_rates, name="exchange_rates"),
    path("", views.home, name="home"),
]
