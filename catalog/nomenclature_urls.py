from django.urls import path

from . import nomenclature_views as views

app_name = "nomenclature"

urlpatterns = [
    path("", views.nomenclature_list, name="list"),
    path("new/", views.product_create, name="create"),
    path("cd/<int:pk>/", views.cd_detail, name="cd_detail"),
    path("tech/<int:pk>/", views.tech_detail, name="tech_detail"),
    path(
        "<str:product_kind>/<int:pk>/media/title/",
        views.product_title_image,
        name="product_title_image",
    ),
    path(
        "<str:product_kind>/<int:pk>/media/title/upload/",
        views.product_title_upload,
        name="product_title_upload",
    ),
    path(
        "<str:product_kind>/<int:pk>/media/title/delete/",
        views.product_title_delete,
        name="product_title_delete",
    ),
    path(
        "<str:product_kind>/<int:pk>/media/images/upload/",
        views.product_gallery_upload,
        name="product_gallery_upload",
    ),
    path(
        "<str:product_kind>/<int:pk>/media/images/<int:image_id>/",
        views.product_gallery_image,
        name="product_gallery_image",
    ),
    path(
        "<str:product_kind>/<int:pk>/media/images/<int:image_id>/delete/",
        views.product_gallery_delete,
        name="product_gallery_delete",
    ),
    path("<str:product_kind>/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path(
        "<str:product_kind>/<int:pk>/barcode/generate/",
        views.barcode_generate,
        name="barcode_generate",
    ),
    path("barcode/<int:barcode_id>/print/", views.barcode_print, name="barcode_print"),
    path(
        "<str:product_kind>/<int:pk>/barcode/print/",
        views.barcode_print_legacy,
        name="barcode_print",
    ),
]
