from django.urls import path

from . import views

app_name = "cash"
urlpatterns = [
    path("<int:warehouse_pk>/", views.register_detail, name="register"),
    path("<int:warehouse_pk>/deposit/", views.deposit, name="deposit"),
    path("<int:warehouse_pk>/collect/", views.collect, name="collect"),
]
