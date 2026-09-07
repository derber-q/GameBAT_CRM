from django.urls import path
from . import views

app_name = "consignment"
urlpatterns = [
    path("", views.consignment_list, name="list"),
    path("transfer/", views.transfer, name="transfer"),
    path("return/", views.return_stock, name="return"),
    path("stocks/<str:product_kind>/<int:pk>/sold/", views.consignment_sale, name="sale"),
    path("movements/<int:pk>/", views.movement_detail, name="movement_detail"),
]
