from django.urls import path
from . import views

app_name = "supplies"
urlpatterns = [
    path("", views.supply_list, name="list"),
    path("new/", views.supply_create, name="create"),
    path("autocomplete/", views.product_autocomplete, name="autocomplete"),
    path("product-weight/", views.supply_product_weight, name="product_weight"),
    path("<int:pk>/cancel/", views.supply_cancel, name="cancel"),
    path("<int:pk>/edit/", views.supply_edit, name="edit"),
    path("<int:pk>/finalization/", views.supply_finalization, name="finalization"),
    path("<int:pk>/finalization/auto/", views.supply_finalization_auto, name="finalization_auto"),
    path("<int:pk>/revisions/<int:revision_number>/", views.supply_revision_detail, name="revision_detail"),
    path("<int:pk>/", views.supply_detail, name="detail"),
]
