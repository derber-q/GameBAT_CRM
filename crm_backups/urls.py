from django.urls import path
from . import api,views,application_views

app_name='crm_backups'
urlpatterns=[
    path('apps/',application_views.applications,name='applications'),
    path('apps/download/<uuid:pk>/',application_views.download,name='app_download'),
    path('',views.dashboard,name='dashboard'),
    path('devices/',views.devices,name='devices'),
    path('api/enroll/',api.registration,name='enroll'),
    path('api/heartbeat/',api.heartbeat,name='heartbeat'),
    path('api/status/',api.status,name='status'),
    path('api/create/',api.create,name='create'),
    path('api/jobs/<uuid:pk>/download/',api.download,name='download'),
    path('api/jobs/<uuid:pk>/confirm/',api.confirm,name='confirm'),
]
