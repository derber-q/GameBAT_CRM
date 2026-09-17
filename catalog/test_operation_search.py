from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import Brand, CD, Platform, ProductType, Tech


class UnifiedOperationSearchTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.other_warehouse = Warehouse.objects.create(name="Другой")
        platform = Platform.objects.create(name="PS5")
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Аксессуары")
        self.cd = CD.objects.create(
            platform=platform, name="Need for Speed Heat PS4", sku="CD-SPEED",
            barcode="001234567890", cusa_ppsa_code="PPSA12345", avito_price=1500,
        )
        self.tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Эльден контроллер",
            sku="TECH-ELDEN", barcode="000000000777", avito_price=2000,
        )
        self.zero_cd = CD.objects.create(
            platform=platform, name="Zero Warehouse Product", sku="CD-ZERO", barcode="00999",
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=3)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.tech, quantity=2)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.zero_cd, quantity=0)
        CDWarehouseStock.objects.create(warehouse=self.other_warehouse, cd=self.zero_cd, quantity=5)
        self.client.force_login(self.actor)
        self.url = reverse("supplies:autocomplete")

    def results(self, query, context="supply", warehouse=None):
        response = self.client.get(self.url, {
            "q": query, "context": context,
            "warehouse": warehouse.pk if warehouse else "",
        })
        self.assertEqual(response.status_code, 200)
        return response.json()["results"]

    def test_partial_name_and_casefold_search_work_for_cd_and_tech(self):
        for query in ("Speed", "HEAT", "speed"):
            self.assertIn(self.cd.pk, [row["id"] for row in self.results(query) if row["type"] == "cd"])
        for query in ("эльден", "ЭЛЬДЕН", "Эльден"):
            self.assertIn(self.tech.pk, [row["id"] for row in self.results(query) if row["type"] == "tech"])

    def test_cusa_and_leading_zero_barcode_work_in_all_stock_contexts(self):
        for context in ("sale", "consignment", "transfer"):
            with self.subTest(context=context):
                by_code = self.results("PPSA12345", context, self.warehouse)
                by_barcode = self.results("001234567890", context, self.warehouse)
                self.assertEqual([row["id"] for row in by_code if row["type"] == "cd"], [self.cd.pk])
                self.assertEqual([row["id"] for row in by_barcode if row["type"] == "cd"], [self.cd.pk])
                self.assertEqual(by_barcode[0]["barcode"], "001234567890")

    def test_supply_allows_zero_stock_but_stock_operations_do_not(self):
        self.assertIn(self.zero_cd.pk, [row["id"] for row in self.results("Zero", "supply")])
        for context in ("sale", "consignment", "transfer"):
            self.assertNotIn(
                self.zero_cd.pk,
                [row["id"] for row in self.results("Zero", context, self.warehouse)],
            )

    def test_sale_results_include_prices_and_search_context_permission_is_enforced(self):
        result = self.results("Speed", "sale", self.warehouse)[0]
        self.assertEqual(result["prices"]["retail"], "1500.00")
        worker = User.objects.create_user("supply-worker", password="StrongWorker!123")
        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="supplies", codename="add_supply",
        ))
        self.client.force_login(worker)
        self.assertEqual(self.client.get(self.url, {
            "q": "Speed", "context": "sale", "warehouse": self.warehouse.pk,
        }).status_code, 403)

    def test_sale_search_before_warehouse_selection_uses_positive_global_stock(self):
        result = self.results("Speed", "sale")[0]
        self.assertEqual(result["id"], self.cd.pk)
        self.assertEqual(result["available"], 3)
        self.assertEqual(result["availability_label"], "Всего в наличии")
        self.assertEqual(result["available_warehouse_ids"], [self.warehouse.pk])
        other_stock_result = self.results("Zero", "sale")[0]
        self.assertEqual(other_stock_result["id"], self.zero_cd.pk)
        self.assertEqual(other_stock_result["available"], 5)
        self.assertEqual(other_stock_result["available_warehouse_ids"], [self.other_warehouse.pk])
        globally_empty_cd = CD.objects.create(
            platform=self.cd.platform,
            name="Globally Empty Product",
            sku="CD-EMPTY",
            barcode="00888",
        )
        CDWarehouseStock.objects.create(
            warehouse=self.warehouse,
            cd=globally_empty_cd,
            quantity=0,
        )
        self.assertNotIn(
            globally_empty_cd.pk,
            [row["id"] for row in self.results("Globally Empty", "sale") if row["type"] == "cd"],
        )

    def test_transfer_page_uses_same_search_and_source_stock_restriction(self):
        self.client.force_login(self.actor)
        url = reverse("warehouse:transfer_create", args=(self.warehouse.pk,))
        response = self.client.get(url, {"search": "PPSA12345"})
        self.assertContains(response, self.cd.name)
        response = self.client.get(url, {"search": "Zero Warehouse"})
        self.assertNotContains(response, self.zero_cd.name)
