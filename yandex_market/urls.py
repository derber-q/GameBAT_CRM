from django.urls import path
from . import views, webhooks, pricing_views

app_name = "yandex_market"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/new/", views.settings_view, name="settings_new"),
    path("settings/<int:pk>/", views.settings_view, name="settings"),
    path("settings/<int:pk>/pricing/", pricing_views.settings_view, name="pricing_settings"),
    path("settings/<int:pk>/check/", views.check, name="check"),
    path("sync/<int:pk>/", views.synchronize, name="sync"),
    path("offers/<int:pk>/bind/", views.bind, name="bind"),
    path("offers/new/", views.new_offer, name="new_offer"),
    path("products/<int:pk>/", views.connection_detail, name="connection"),
    path("products/<int:pk>/categories/", views.categories, name="categories"),
    path("products/<int:pk>/action/", views.content_action, name="content_action"),
    path("products/<int:pk>/unlink/", views.unlink, name="unlink"),
    path("orders/<int:pk>/", views.order_detail, name="order"),
    path("orders/<int:pk>/action/", views.order_action, name="order_action"),
    path("returns/<int:pk>/accept/", views.return_accept, name="return_accept"),
    path("labels/request/", views.label_request, name="label_request"),
    path("labels/<int:pk>/", views.label_detail, name="label"),
    path("labels/<int:pk>/file/", views.label_file, name="label_file"),
    path("jobs/<int:pk>/retry/", views.retry, name="retry"),
    path("media/<uuid:public_id>/", views.public_media, name="media"),
    path("notifications/", webhooks.notification, name="notifications"),
]
