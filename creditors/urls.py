"""Именованные HTTP-маршруты приложения задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны."""
from django.urls import path

from . import views

app_name = "creditors"
urlpatterns = [
    path("", views.creditor_list, name="list"),
    path("operations/<int:pk>/", views.creditor_operation, name="operation"),
    path("prepayment-operations/<int:pk>/", views.creditor_operation, {"prepayment": True}, name="prepayment_operation"),
    path("new/", views.creditor_create, name="create"),
    path("<int:pk>/", views.creditor_detail, name="detail"),
    path("<int:pk>/edit/", views.creditor_edit, name="edit"),
    path("<int:pk>/debt/", views.creditor_debt, name="debt"),
    path("<int:pk>/prepayment/", views.creditor_prepayment, name="prepayment"),
    path("<int:pk>/prepayment/transfer/", views.creditor_prepayment, {"transfer": True}, name="prepayment_transfer"),
]
