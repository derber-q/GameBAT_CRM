from django.urls import path
from . import views

app_name = "consignment"
urlpatterns = [
    path("", views.consignment_list, name="list"),
    path("platform/<int:pk>/", views.consignment_platform, name="platform"),
    path("transfer/", views.transfer, name="transfer"),
    path("return/", views.return_stock, name="return"),
    path("stocks/<str:product_kind>/<int:pk>/reward/", views.reward_update, name="reward_update"),
    path("stocks/<str:product_kind>/<int:pk>/sold/", views.consignment_sale, name="sale"),
    path("stocks/<str:product_kind>/<int:pk>/action/", views.row_action, name="row_action"),
    path("movements/<int:pk>/", views.movement_detail, name="movement_detail"),
]
