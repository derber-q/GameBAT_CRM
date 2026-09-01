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
        response = self.client.get(reverse("catalog:warehouse"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.platform.name)
        self.assertContains(response, self.product_type.name)
        self.assertContains(response, "Диск")
        self.assertContains(response, "Техника")
