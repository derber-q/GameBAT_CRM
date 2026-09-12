import re

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .models import Brand, CD, Platform, ProductType, Tech


class ProductBrowsingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("product-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Основной склад")
        self.ps5 = Platform.objects.create(name="PlayStation 5")
        self.ps4 = Platform.objects.create(name="PlayStation 4")
        self.apple = Brand.objects.create(name="Apple")
        self.samsung = Brand.objects.create(name="Samsung")
        self.phone = ProductType.objects.create(name="Смартфоны")
        self.laptop = ProductType.objects.create(name="Ноутбуки")
        self.ps5_cd = CD.objects.create(
            platform=self.ps5,
            name="Elden Ring Pro Edition",
            sku="CD-ELDEN-PRO",
            barcode="4600000001001",
            cusa_ppsa_code="PPSA-ELDEN-1001",
            cost=100,
        )
        self.ps4_cd = CD.objects.create(
            platform=self.ps4,
            name="Другая игра",
            sku="CD-OTHER",
            barcode="4600000001002",
            cusa_ppsa_code="CUSA-OTHER-1002",
            cost=90,
        )
        self.iphone = Tech.objects.create(
            brand=self.apple, product_type=self.phone, name="iPhone Pro",
            sku="TECH-IPHONE-PRO", barcode="4600000002001", cost=500,
        )
        self.macbook = Tech.objects.create(
            brand=self.apple, product_type=self.laptop, name="MacBook Pro",
            sku="TECH-MACBOOK-PRO", barcode="4600000002002", cost=700,
        )
        self.galaxy = Tech.objects.create(
            brand=self.samsung, product_type=self.phone, name="Galaxy Pro",
            sku="TECH-GALAXY-PRO", barcode="4600000002003", cost=450,
        )
        self.zero_stock = Tech.objects.create(
            brand=self.apple, product_type=self.phone, name="iPhone Zero Stock",
            sku="TECH-ZERO-STOCK", barcode="4600000002004", cost=400,
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.ps5_cd, quantity=2)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.ps4_cd, quantity=3)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.iphone, quantity=4)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.macbook, quantity=2)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.galaxy, quantity=1)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.zero_stock, quantity=0)
        self.client.force_login(self.user)
        self.urls = (
            reverse("warehouse:global_stock"),
            reverse("warehouse:detail", args=(self.warehouse.pk,)),
            reverse("nomenclature:list"),
            reverse("pricing:list"),
        )

    def test_search_supports_all_identifiers_on_every_product_page(self):
        for url in self.urls:
            for query in (
                "elden ring",
                "CD-ELDEN",
                "4600000001001",
                "PPSA-ELDEN",
                str(self.ps5_cd.pk),
            ):
                with self.subTest(url=url, query=query):
                    response = self.client.get(url, {"search": query})
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, self.ps5_cd.name)

    def test_platform_filter_returns_only_matching_cd_on_every_page(self):
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url, {"platform": self.ps5.pk})
                self.assertContains(response, self.ps5_cd.name)
                self.assertNotContains(response, self.ps4_cd.name)
                self.assertNotContains(response, self.iphone.name)
                self.assertEqual(response.context["filter_state"].platform_id, self.ps5.pk)

    def test_brand_type_and_search_combine_for_tech_on_every_page(self):
        params = {"search": "iphone", "brand": self.apple.pk, "product_type": self.phone.pk}
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url, params)
                self.assertContains(response, self.iphone.name)
                self.assertNotContains(response, self.macbook.name)
                self.assertNotContains(response, self.galaxy.name)
                self.assertNotContains(response, self.ps5_cd.name)

    def test_platform_wins_for_a_manually_conflicting_url(self):
        params = {
            "platform": self.ps5.pk,
            "brand": self.apple.pk,
            "product_type": self.phone.pk,
        }
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url, params)
                state = response.context["filter_state"]
                self.assertEqual(state.platform_id, self.ps5.pk)
                self.assertIsNone(state.brand_id)
                self.assertIsNone(state.product_type_id)
                self.assertContains(response, self.ps5_cd.name)
                self.assertNotContains(response, self.iphone.name)

    def test_zero_stock_visibility_keeps_each_pages_existing_rule(self):
        self.assertNotContains(
            self.client.get(reverse("warehouse:detail", args=(self.warehouse.pk,))),
            self.zero_stock.name,
        )
        self.assertContains(self.client.get(reverse("warehouse:global_stock")), self.zero_stock.name)
        self.assertContains(self.client.get(reverse("nomenclature:list")), self.zero_stock.name)
        self.assertContains(self.client.get(reverse("pricing:list")), self.zero_stock.name)

    def test_filter_state_options_reset_and_collapsible_groups_are_rendered(self):
        params = {"search": "iphone", "brand": self.apple.pk, "product_type": self.phone.pk}
        response = self.client.get(reverse("nomenclature:list"), params)
        self.assertContains(response, 'name="search" value="iphone"')
        self.assertContains(response, f'<option value="{self.apple.pk}" selected>Apple</option>', html=True)
        self.assertContains(
            response,
            f'<option value="{self.phone.pk}" selected>Смартфоны</option>',
            html=True,
        )
        self.assertContains(response, f'href="{reverse("nomenclature:list")}"')

        for url in self.urls:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                controls = re.findall(r'aria-controls="([^"]+)"[^>]*data-collapse-toggle', html)
                content_ids = re.findall(r'id="((?:global|warehouse|nomenclature|pricing)-(?:cd|tech)-\d+)"', html)
                self.assertGreater(len(controls), 0)
                self.assertEqual(len(controls), len(set(controls)))
                self.assertCountEqual(controls, content_ids)
                self.assertEqual(html.count('aria-expanded="true"'), len(controls))

    def test_empty_result_does_not_render_empty_category_sections(self):
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url, {"search": "NO-SUCH-PRODUCT"})
                self.assertContains(response, "Товары по заданным параметрам не найдены")
                self.assertNotContains(response, "collapsible-section")
