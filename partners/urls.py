from django.urls import path
from . import views

app_name = "partners"
urlpatterns = [
    path("", views.supplier_list, name="list"),
    path("new/", views.supplier_create, name="create"),
    path("<int:pk>/edit/", views.supplier_update, name="update"),
]
