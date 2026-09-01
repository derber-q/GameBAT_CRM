from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import SalesPlatform, Supplier


class InternalPageSmokeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоль")
        CD.objects.create(platform=platform, name="Игра", sku="CD-1", barcode="001")
        Tech.objects.create(brand=brand, product_type=product_type, name="Консоль", sku="T-1", barcode="002")
        Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО Поставщик", phone_1="+70000000000",
        )
        SalesPlatform.objects.create(
            name="Площадка", address="Адрес", legal_entity="ООО Площадка", phone_1="+70000000001"
        )
        self.client.force_login(self.admin)

    def test_primary_get_pages_render(self):
        urls = (
            reverse("catalog:warehouse"),
            reverse("partners:list"),
            reverse("partners:create"),
            reverse("supplies:list"),
            reverse("supplies:create"),
            reverse("consignment:list"),
            reverse("consignment:transfer"),
            reverse("consignment:return"),
            reverse("accounts:user_list"),
            reverse("accounts:permission_sets"),
            reverse("accounts:password_change"),
            reverse("admin:index"),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_is_forced_to_light_theme(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "admin/js/theme.js")
        self.assertNotContains(response, "theme-toggle")
