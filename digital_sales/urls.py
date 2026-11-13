from django.urls import path
from . import views

app_name = 'digital_sales'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('buyers/new/', views.buyer_edit, name='buyer_create'),
    path('buyers/<int:pk>/', views.buyer_edit, name='buyer_edit'),
    path('balance/', views.balance, name='balance'),
    path('new/', views.manual, name='manual'),
    path('configuration/', views.configuration, name='configuration'),
    path('orders/<int:pk>/', views.order_detail, name='order'),
    path('orders/<int:pk>/action/', views.order_action, name='action'),
    path('messages/<int:pk>/reveal/', views.reveal, name='reveal'),
    path('messages/<int:pk>/files/<int:index>/', views.download, name='download'),
]
