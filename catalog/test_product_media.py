import shutil
import tempfile
from io import BytesIO

from PIL import Image
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from warehouse.models import CDWarehouseStock, Warehouse

from .models import CD, Platform, ProductImage


def uploaded_image(name="product.png", *, color=(44, 135, 155)):
    output = BytesIO()
    Image.new("RGB", (32, 24), color).save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


class ProductMediaTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.user = User.objects.create_superuser(
            "product-media-admin", password="StrongAdmin!123",
        )
        self.client.force_login(self.user)
        self.platform = Platform.objects.create(name="Фото-платформа")
        self.product = CD.objects.create(
            platform=self.platform, name="Товар с фотографиями", sku="PHOTO-1",
        )
        self.warehouse = Warehouse.objects.create(name="Фото-склад")
        CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=1,
        )

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_title_image_is_saved_served_and_added_to_hover_links(self):
        response = self.client.post(
            reverse("nomenclature:product_title_upload", args=("cd", self.product.pk)),
            {"image": uploaded_image()},
        )
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertTrue(self.product.title_image.name)

        image_url = reverse(
            "nomenclature:product_title_image", args=("cd", self.product.pk),
        )
        image_response = self.client.get(image_url)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response["Content-Type"], "image/png")
        self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")

        for page in (
            reverse("nomenclature:list"),
            reverse("warehouse:global_stock"),
            reverse("warehouse:detail", args=(self.warehouse.pk,)),
            reverse("pricing:list"),
        ):
            response = self.client.get(page)
            self.assertContains(response, f'data-product-title-image="{image_url}"')

    def test_gallery_keeps_additional_and_product_images_separate(self):
        upload_url = reverse(
            "nomenclature:product_gallery_upload", args=("cd", self.product.pk),
        )
        self.client.post(upload_url, {
            "image_kind": ProductImage.ImageKind.ADDITIONAL,
            "images": [uploaded_image("extra-1.png"), uploaded_image("extra-2.png")],
        })
        self.client.post(upload_url, {
            "image_kind": ProductImage.ImageKind.PRODUCT,
            "images": [uploaded_image("promo.png")],
        })

        self.assertEqual(
            self.product.catalog_images.filter(
                image_kind=ProductImage.ImageKind.ADDITIONAL,
            ).count(),
            2,
        )
        promo = self.product.catalog_images.get(
            image_kind=ProductImage.ImageKind.PRODUCT,
        )
        image_url = reverse(
            "nomenclature:product_gallery_image",
            args=("cd", self.product.pk, promo.pk),
        )
        self.assertEqual(self.client.get(image_url).status_code, 200)
        detail = self.client.get(reverse("nomenclature:cd_detail", args=(self.product.pk,)))
        self.assertContains(detail, "Дополнительные фото")
        self.assertContains(detail, "Изображения продукта")
        self.assertContains(detail, image_url)

    def test_invalid_upload_is_rejected_without_creating_media(self):
        response = self.client.post(
            reverse("nomenclature:product_title_upload", args=("cd", self.product.pk)),
            {"image": SimpleUploadedFile(
                "fake.png", b"not-an-image", content_type="image/png",
            )},
            follow=True,
        )
        self.product.refresh_from_db()
        self.assertFalse(self.product.title_image)
        self.assertContains(response, "Файл не является корректным изображением")

    def test_gallery_image_cannot_be_deleted_through_another_product(self):
        other = CD.objects.create(
            platform=self.platform, name="Другой товар", sku="PHOTO-2",
        )
        self.client.post(
            reverse("nomenclature:product_gallery_upload", args=("cd", self.product.pk)),
            {
                "image_kind": ProductImage.ImageKind.ADDITIONAL,
                "images": [uploaded_image()],
            },
        )
        item = self.product.catalog_images.get()
        response = self.client.post(reverse(
            "nomenclature:product_gallery_delete",
            args=("cd", other.pk, item.pk),
        ))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProductImage.objects.filter(pk=item.pk).exists())

    def test_reader_can_view_but_cannot_change_media(self):
        reader = User.objects.create_user("product-media-reader", password="ReaderPass!123")
        permission = Permission.objects.get(
            content_type__app_label="catalog", codename="view_nomenclature",
        )
        reader.user_permissions.add(permission)
        self.client.force_login(reader)

        detail = self.client.get(reverse("nomenclature:cd_detail", args=(self.product.pk,)))
        self.assertEqual(detail.status_code, 200)
        response = self.client.post(
            reverse("nomenclature:product_title_upload", args=("cd", self.product.pk)),
            {"image": uploaded_image()},
        )
        self.assertEqual(response.status_code, 403)
