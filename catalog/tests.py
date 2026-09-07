from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Brand, CD, Platform, ProductType, Tech


class WarehouseGroupingTests(TestCase):
    def setUp(self):
        self.worker = User.objects.create_user("worker", password="StrongWorker!123")
        self.worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="view_cd"),
            Permission.objects.get(content_type__app_label="catalog", codename="view_tech"),
        )
        self.platform = Platform.objects.create(name="Динамическая платформа")
        self.product_type = ProductType.objects.create(name="Динамический тип")
        brand = Brand.objects.create(name="Бренд")
        CD.objects.create(platform=self.platform, name="Диск", sku="D-1", barcode="1")
        Tech.objects.create(brand=brand, product_type=self.product_type, name="Техника", sku="T-1", barcode="2")
        self.client.force_login(self.worker)

    def test_cd_is_grouped_by_platform_and_tech_by_product_type(self):
        empty_type = ProductType.objects.create(name="Empty product type")
        response = self.client.get(reverse("catalog:warehouse"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.platform.name)
        self.assertContains(response, self.product_type.name)
        self.assertNotContains(response, empty_type.name)
        self.assertContains(response, "Диск")
        self.assertContains(response, "Техника")

    def test_legacy_product_permissions_do_not_reveal_the_other_catalog(self):
        self.worker.user_permissions.remove(
            Permission.objects.get(content_type__app_label="catalog", codename="view_tech")
        )
        response = self.client.get(reverse("catalog:warehouse"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Диск")
        self.assertNotContains(response, "Техника")


class OptionalBarcodeTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="Платформа без штрихкода")
        self.brand = Brand.objects.create(name="Бренд без штрихкода")
        self.product_type = ProductType.objects.create(name="Тип без штрихкода")

    def test_cd_and_tech_allow_blank_barcode(self):
        cd = CD(platform=self.platform, name="Диск", sku="CD-NO-BARCODE", barcode="")
        tech = Tech(
            brand=self.brand,
            product_type=self.product_type,
            name="Техника",
            sku="TECH-NO-BARCODE",
            barcode="",
        )

        cd.full_clean()
        tech.full_clean()
        cd.save()
        tech.save()

        self.assertEqual(cd.barcode, "")
        self.assertEqual(tech.barcode, "")
