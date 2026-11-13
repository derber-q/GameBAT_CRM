from django.urls import path
from . import views

app_name = 'digital_prices'
urlpatterns = [path('', views.catalog, name='catalog'), path('sync/', views.sync, name='sync'),
    path('manual/', views.manual, name='manual'),
    path('manual/<int:pk>/amounts/', views.manual_amounts, name='manual_amounts'),
    path('status/', views.status, name='status'),
    path('configuration/', views.configuration, name='configuration'), path('markup/<int:pk>/', views.markup, name='markup'),
    path('layout/<int:pk>/', views.layout, name='layout'), path('generate/', views.generate, name='generate'),
    path('preview/<uuid:pk>/', views.preview, name='preview'), path('png/<int:pk>/', views.png, name='png'),
    path('download/<uuid:pk>/', views.download, name='download')]
