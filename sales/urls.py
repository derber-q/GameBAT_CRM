from django.urls import path

from . import views

app_name = "sales"
urlpatterns = [
    path("", views.sale_list, name="list"),
    path("incomplete/", views.sale_list, name="incomplete"),
    path("completed/", views.sale_completed_list, name="completed"),
    path("cancelled/", views.sale_cancelled_list, name="cancelled"),
    path("<int:pk>/status/", views.sale_inline_status, name="inline_status"),
    path("new/", views.sale_create, name="create"),
    path("new/import-wholesale/", views.sale_wholesale_import, name="import_wholesale"),
    path("<int:pk>/", views.sale_detail, name="detail"),
    path("<int:pk>/edit/", views.sale_edit, name="edit"),
    path("<int:pk>/advance/", views.sale_advance, name="advance"),
    path("<int:pk>/mark-paid/", views.sale_mark_paid, name="mark_paid"),
    path("<int:pk>/note/", views.sale_note_update, name="note_update"),
    path("<int:pk>/cancel/", views.sale_cancel, name="cancel"),
]
