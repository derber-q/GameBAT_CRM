from django.urls import path

from . import views

app_name = "creditors"
urlpatterns = [
    path("", views.creditor_list, name="list"),
    path("new/", views.creditor_create, name="create"),
    path("<int:pk>/", views.creditor_detail, name="detail"),
    path("<int:pk>/edit/", views.creditor_edit, name="edit"),
    path("<int:pk>/debt/", views.creditor_debt, name="debt"),
]
