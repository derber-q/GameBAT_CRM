from django.urls import path

from . import views

app_name = "cash"
urlpatterns = [
    path("<int:warehouse_pk>/", views.register_detail, name="register"),
    path("<int:warehouse_pk>/deposit/", views.deposit, name="deposit"),
    path("<int:warehouse_pk>/collect/", views.collect, name="collect"),
    path("<int:warehouse_pk>/safe/deposit/", views.safe_deposit, name="safe_deposit"),
    path("<int:warehouse_pk>/safe/collect/", views.safe_collect, name="safe_collect"),
    path("<int:warehouse_pk>/transfer/cash-to-safe/", views.cash_to_safe, name="cash_to_safe"),
    path("<int:warehouse_pk>/transfer/safe-to-cash/", views.safe_to_cash, name="safe_to_cash"),
]
