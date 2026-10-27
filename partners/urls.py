from django.urls import path
from . import views
from . import partner_views

app_name = "partners"
urlpatterns = [
    path('partners/', partner_views.partner_list, name='partner_list'),
    path('partners/new/', partner_views.partner_create, name='partner_create'),
    path('partners/<int:pk>/', partner_views.partner_detail, name='partner_detail'),
    path('partners/<int:pk>/edit/', partner_views.partner_edit, name='partner_edit'),
    path("", views.supplier_list, name="list"),
    path("new/", views.supplier_create, name="create"),
    path("<int:pk>/edit/", views.supplier_update, name="update"),
]
