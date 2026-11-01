"""Фиксированный протокол исходящих запросов магазинного агента."""
from django.urls import path
from . import print_agent_views as views

urlpatterns = [
    path('heartbeat/', views.heartbeat),
    path('claim/', views.claim),
    path('jobs/<uuid:request_id>/document/', views.document),
    path('jobs/<uuid:request_id>/result/', views.result),
]
