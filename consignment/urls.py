from django.urls import path
from . import views

app_name = "consignment"
urlpatterns = [
    path("", views.consignment_list, name="list"),
    path("transfer/", views.transfer, name="transfer"),
    path("return/", views.return_stock, name="return"),
]
