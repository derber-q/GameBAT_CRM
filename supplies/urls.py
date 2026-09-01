from django.urls import path
from . import views

app_name = "supplies"
urlpatterns = [
    path("", views.supply_list, name="list"),
    path("new/", views.supply_create, name="create"),
    path("autocomplete/", views.product_autocomplete, name="autocomplete"),
    path("<int:pk>/", views.supply_detail, name="detail"),
]
