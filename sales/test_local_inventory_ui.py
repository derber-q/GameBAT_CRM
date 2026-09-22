from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from warehouse.models import (
    CDWarehouseStock, CDWarehouseStorageAssignment,
    TechWarehouseStock,
    Warehouse, WarehouseStorageLocation,
)


class SaleLocalInventoryUiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("sale-local-admin", password="StrongAdmin!123")
        self.warehouse_a = Warehouse.objects.create(name="Склад A")
        self.warehouse_b = Warehouse.objects.create(name="Склад B")
        platform = Platform.objects.create(name="PS5 local stock")
        brand = Brand.objects.create(name="Sony local stock")
        product_type = ProductType.objects.create(name="Контроллер local stock")
        self.cd = CD.objects.create(
            platform=platform, name="Игра с местами", sku="LOCAL-CD", barcode="LOCAL-CD-BC",
            avito_price=1000,
        )
        self.tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Техника без места",
            sku="LOCAL-TECH", barcode="LOCAL-TECH-BC", avito_price=2000,
        )
        cd_stock_a = CDWarehouseStock.objects.create(warehouse=self.warehouse_a, cd=self.cd, quantity=10)
        cd_stock_b = CDWarehouseStock.objects.create(warehouse=self.warehouse_b, cd=self.cd, quantity=2)
        TechWarehouseStock.objects.create(warehouse=self.warehouse_a, tech=self.tech, quantity=3)
        location_a1 = WarehouseStorageLocation.objects.create(
            warehouse=self.warehouse_a, room="A", rack=1, shelf=2, columns=[1, 2]
        )
        location_a2 = WarehouseStorageLocation.objects.create(
            warehouse=self.warehouse_a, room="A", rack=6, shelf=3, columns=[]
        )
        location_b = WarehouseStorageLocation.objects.create(
            warehouse=self.warehouse_b, room="B", rack=4, shelf=3, columns=[]
        )
        CDWarehouseStorageAssignment.objects.create(stock=cd_stock_a, location=location_a1, position=0)
        CDWarehouseStorageAssignment.objects.create(stock=cd_stock_a, location=location_a2, position=1)
        CDWarehouseStorageAssignment.objects.create(stock=cd_stock_b, location=location_b, position=0)
        self.client.force_login(self.user)

    def autocomplete(self, **params):
        return self.client.get(
            reverse("supplies:autocomplete"), {"context": "sale", **params}
        )

    def test_cd_result_contains_selected_warehouse_stock_and_multiple_locations(self):
        response = self.autocomplete(q="Игра с местами", warehouse=self.warehouse_a.pk)
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["type"], "cd")
        self.assertEqual(result["warehouse_stock"], 10)
        self.assertEqual(result["available"], 10)
        self.assertEqual(result["storage_locations"], "A1-2-1\\2, A6-3")

    def test_tech_result_without_location_returns_empty_location_and_local_stock(self):
        response = self.autocomplete(q="Техника без места", warehouse=self.warehouse_a.pk)
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["type"], "tech")
        self.assertEqual(result["warehouse_stock"], 3)
        self.assertEqual(result["storage_locations"], "")

    def test_batch_refresh_uses_new_warehouse_and_includes_zero_stock_rows(self):
        response = self.autocomplete(
            warehouse=self.warehouse_b.pk,
            items=f"cd:{self.cd.pk},tech:{self.tech.pk}",
        )
        self.assertEqual(response.status_code, 200)
        by_type = {result["type"]: result for result in response.json()["results"]}
        self.assertEqual(by_type["cd"]["warehouse_stock"], 2)
        self.assertEqual(by_type["cd"]["storage_locations"], "B4-3")
        self.assertEqual(by_type["tech"]["warehouse_stock"], 0)
        self.assertEqual(by_type["tech"]["storage_locations"], "")

    def test_invalid_warehouse_and_invalid_batch_are_rejected(self):
        self.assertEqual(self.autocomplete(q="Игра", warehouse=999999).status_code, 404)
        self.assertEqual(
            self.autocomplete(warehouse=self.warehouse_a.pk, items="supplier:1").status_code, 400
        )

    def test_sale_page_contains_local_inventory_columns_and_fresh_script(self):
        response = self.client.get(reverse("sales:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Остаток на складе")
        self.assertContains(response, "Доступно ещё")
        self.assertContains(response, "Место хранения")
        self.assertContains(response, 'data-show-sale-inventory="true"')
        self.assertContains(response, "stock-lines.js?v=global-barcode-1")

    def test_frontend_aggregates_duplicate_quantities_and_refreshes_on_warehouse_change(self):
        script = (settings.STATICFILES_DIRS[0] / "js" / "stock-lines.js").read_text(encoding="utf-8")
        self.assertIn("selectedQuantities", script)
        self.assertIn("stock - selected", script)
        self.assertIn('warehouseInput.addEventListener("change", refreshInventory)', script)
        self.assertIn("items: refs.join", script)
