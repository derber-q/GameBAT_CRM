from django.urls import path
from . import views

app_name = 'wholesale_bot'
urlpatterns = [
    path('service-state/', views.service_state, name='service_state'),
    path('', views.dashboard, name='dashboard'),
    path('configuration/', views.configuration, name='configuration'),
    path('customers/<int:pk>/', views.customer_action, name='customer_action'),
    path('retry/<str:kind>/<int:pk>/', views.retry, name='retry'),
    path('orders/<uuid:pk>/original/', views.original, name='original'),
]
