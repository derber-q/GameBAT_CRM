from django.urls import path
from . import views

app_name = 'digital_shop'
urlpatterns = [path('', views.dashboard, name='dashboard'), path('orders/<uuid:pk>/', views.order_detail, name='order')]
