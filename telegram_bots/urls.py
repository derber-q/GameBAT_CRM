from django.urls import path
from . import views

app_name = 'telegram_bots'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('connect/', views.connection, name='connection'),
]
