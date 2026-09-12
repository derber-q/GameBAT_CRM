from django.urls import path

from . import nomenclature_views as views

app_name = "nomenclature"

urlpatterns = [
    path("", views.nomenclature_list, name="list"),
    path("new/", views.product_create, name="create"),
    path("cd/<int:pk>/", views.cd_detail, name="cd_detail"),
    path("tech/<int:pk>/", views.tech_detail, name="tech_detail"),
]
