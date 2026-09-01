from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/change/", views.password_change, name="password_change"),
    path("users/", views.user_list, name="user_list"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/edit/", views.user_update, name="user_update"),
    path("users/<int:pk>/reset-password/", views.admin_password_reset, name="password_reset"),
    path("users/<int:pk>/document/", views.verification_document, name="verification_document"),
    path("permission-sets/", views.permission_set_list, name="permission_sets"),
    path("permission-sets/new/", views.permission_set_edit, name="permission_set_create"),
    path("permission-sets/<int:pk>/edit/", views.permission_set_edit, name="permission_set_edit"),
    path("permission-sets/<int:pk>/delete/", views.permission_set_delete, name="permission_set_delete"),
]
