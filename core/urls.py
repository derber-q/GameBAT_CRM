from django.urls import path
from . import views

app_name = "core"
urlpatterns = [
    path("api/exchange-rates/", views.exchange_rates, name="exchange_rates"),
    path("", views.home, name="home"),
]
