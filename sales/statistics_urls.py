from django.urls import path

from . import statistics_views

app_name = "statistics"
urlpatterns = [
    path("", statistics_views.statistics_index, name="index"),
    path("export/", statistics_views.statistics_export, name="export"),
]
