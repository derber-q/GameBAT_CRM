from django.urls import path

from . import views

app_name = "sales"
urlpatterns = [
    path("", views.sale_list, name="list"),
    path("new/", views.sale_create, name="create"),
    path("<int:pk>/", views.sale_detail, name="detail"),
    path("<int:pk>/edit/", views.sale_edit, name="edit"),
    path("<int:pk>/advance/", views.sale_advance, name="advance"),
    path("<int:pk>/mark-paid/", views.sale_mark_paid, name="mark_paid"),
]
