from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from consignment.services import transfer_to_consignment
from partners.models import SalesPlatform, Supplier
from sales.models import Sale
from sales.services import cancel_sale, create_sale
from supplies.services import accept_supply, cancel_supply

from .models import (
    CDWarehouseStock,
    TechWarehouseStock,
    Warehouse,
    WarehouseStorageLocation,
)
from .services import advance_transfer_status, create_transfer
from .storage_locations import (
    normalize_storage_location_list,
    parse_storage_location_list,
    parse_storage_location_query,
)
from .storage_services import update_storage_locations


class StorageLocationParserTests(TestCase):
    def test_new_format_normalization(self):
        cases = {
            r"a1 - 2 - 2 \ 1": r"A1-2-1\2",
            "A1–2–1\\2": r"A1-2-1\2",
            r"A1-2-1\2,A6-3": r"A1-2-1\2, A6-3",
            r"A1 - 2 , B3 - 4 - 2 \ 1": r"A1-2, B3-4-1\2",
            r"A1-2-3\1\3\2": r"A1-2-1\2\3",
            "A1-2, a1 - 2, A1-2": "A1-2",
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(normalize_storage_location_list(raw_value), expected)

    def test_valid_values(self):
        for value in (
            "A1-2", "A1-2-1", r"A1-2-1\2", r"A1-2-1\2\3", "B12-6",
            "B12-6-1", r"Z25-10-4\5\10", r"A1-2-1\2, A6-3",
        ):
            with self.subTest(value=value):
                self.assertTrue(parse_storage_location_list(value))

    def test_invalid_and_old_values(self):
        for value in (
            "A", "A1", "A-1-2", "1A-2", "A1-", "A1-2-", "A1-2-X",
            "A1-2-1\\", "A1-2-\\1", "A1-2-1\\\\2", "A1-2-1,2",
            "A0-2", "A1-0", "A1-2-0", "A1-2-1\\0", "A1-2 A6-3", "A1-2;A6-3",
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_storage_location_list(value)

    def test_filter_query_is_structured(self):
        self.assertEqual(parse_storage_location_query("a1").rack, 1)
        self.assertEqual(parse_storage_location_query("A1-2").shelf, 2)
        self.assertEqual(parse_storage_location_query(r"A1-2-2\1").columns, (1, 2))


class StorageLocationFeatureTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.worker = User.objects.create_user("worker", password="StrongWorker!123")
        self.platform = Platform.objects.create(name="PS5")
        self.brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="Консоль")
        self.cd = CD.objects.create(
            platform=self.platform, name="Игра", sku="CD-1", barcode="1", retail_price=100, cost=100,
        )
        self.other_cd = CD.objects.create(
            platform=self.platform, name="Другая игра", sku="CD-2", barcode="2", retail_price=100, cost=100,
        )
        self.tech = Tech.objects.create(
            brand=self.brand, product_type=self.product_type, name="Приставка", sku="TECH-1", retail_price=200,
        )
        self.warehouse = Warehouse.objects.create(name="Москва")
        self.other_warehouse = Warehouse.objects.create(name="СПб")
        self.cd_stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=3)
        self.other_cd_stock = CDWarehouseStock.objects.create(
            warehouse=self.other_warehouse, cd=self.cd, quantity=3,
        )
        self.second_cd_stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.other_cd, quantity=2,
        )
        self.tech_stock = TechWarehouseStock.objects.create(
            warehouse=self.warehouse, tech=self.tech, quantity=2,
        )

    def assign(self, value, *, warehouse=None, product_type="cd", product=None):
        warehouse = warehouse or self.warehouse
        product = product or (self.cd if product_type == "cd" else self.tech)
        return update_storage_locations(
            actor=self.actor,
            warehouse_id=warehouse.pk,
            product_type=product_type,
            product_id=product.pk,
            raw_value=value,
        )

    def test_save_reload_duplicates_order_and_audit(self):
        result = self.assign(r"a1 - 2 - 2 \ 1, A6-3, A1-2-1\2")
        self.assertEqual(result.value, r"A1-2-1\2, A6-3")
        assignments = list(self.cd_stock.storage_assignments.select_related("location"))
        self.assertEqual([row.location.canonical_value for row in assignments], [r"A1-2-1\2", "A6-3"])
        self.assertEqual(WarehouseStorageLocation.objects.filter(warehouse=self.warehouse).count(), 2)
        event = self.cd.change_events.order_by("-pk").first()
        change = event.field_changes.get()
        self.assertEqual(change.old_value, "")
        self.assertEqual(change.new_value, r"A1-2-1\2, A6-3")
        self.assertEqual(event.actor, self.actor)

    def test_warehouse_and_product_type_isolation(self):
        self.assign("A1-2")
        self.assign("B3-4", warehouse=self.other_warehouse)
        self.assign("A1-2", product_type="tech")
        self.assertEqual(WarehouseStorageLocation.objects.filter(canonical_value="A1-2").count(), 1)
        self.assertEqual(self.cd_stock.storage_assignments.get().location.canonical_value, "A1-2")
        self.assertEqual(self.other_cd_stock.storage_assignments.get().location.canonical_value, "B3-4")
        self.assertEqual(self.tech_stock.storage_assignments.get().location.canonical_value, "A1-2")
        self.assertEqual(
            self.cd_stock.storage_assignments.get().location_id,
            self.tech_stock.storage_assignments.get().location_id,
        )

    def test_invalid_save_is_atomic_and_empty_value_is_allowed(self):
        self.assign("A1-2")
        with self.assertRaises(ValidationError):
            self.assign("A1-2-1,2")
        self.assertEqual(self.cd_stock.storage_assignments.get().location.canonical_value, "A1-2")
        result = self.assign("")
        self.assertEqual(result.value, "")
        self.assertFalse(self.cd_stock.storage_assignments.exists())

    def test_permission_inline_ui_post_only_and_server_validation(self):
        self.assign(r"A1-2-1\2")
        self.worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="warehouse", codename="view_warehouse_stock")
        )
        self.client.force_login(self.worker)
        detail_url = reverse("warehouse:detail", args=(self.warehouse.pk,))
        update_url = reverse("warehouse:storage_location_update", args=(self.warehouse.pk, "cd", self.cd.pk))
        response = self.client.get(detail_url)
        self.assertContains(response, r"A1-2-1\2")
        self.assertNotContains(response, "data-storage-location-form")
        self.assertEqual(self.client.post(update_url, {"storage_location": "A2-3"}).status_code, 403)

        self.worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="warehouse", codename="change_storage_location")
        )
        self.client.force_login(self.worker)
        self.assertContains(self.client.get(detail_url), "data-storage-location-form")
        self.assertEqual(self.client.get(update_url).status_code, 405)
        invalid = self.client.post(update_url, {"storage_location": "A1-2-1,2"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["field"], "storage_location")
        saved = self.client.post(update_url, {"storage_location": "a2 - 3"})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["value"], "A2-3")

    def test_autocomplete_current_warehouse_last_token_and_active_locations(self):
        self.assign("A1-1")
        self.assign("A10-2", product=self.other_cd)
        self.assign("B2-1", product_type="tech")
        self.assign("A1-99", warehouse=self.other_warehouse)
        self.client.force_login(self.actor)
        url = reverse("warehouse:storage_location_autocomplete", args=(self.warehouse.pk,))
        values = [row["value"] for row in self.client.get(url, {"q": "A1"}).json()["results"]]
        self.assertEqual(values, ["A1-1"])
        self.assertNotIn("A10-2", values)
        self.assertNotIn("A1-99", values)
        values = [row["value"] for row in self.client.get(url, {"q": "Z9-1, B"}).json()["results"]]
        self.assertEqual(values, ["B2-1"])

    def test_location_filter_is_structured_and_combines_with_product_filters(self):
        self.assign(r"A1-2-1\2\3")
        self.assign("A10-2", product=self.other_cd)
        self.assign("B3-4", product_type="tech")
        self.client.force_login(self.actor)
        url = reverse("warehouse:detail", args=(self.warehouse.pk,))

        rack = self.client.get(url, {"location": "A1"})
        self.assertContains(rack, self.cd.name)
        self.assertNotContains(rack, self.other_cd.name)
        column = self.client.get(url, {"location": "A1-2-2"})
        self.assertContains(column, self.cd.name)
        self.assertNotContains(self.client.get(url, {"location": "A1-2-4"}), self.cd.name)
        combined = self.client.get(url, {
            "search": "Игра", "location": "A1", "platform": str(self.platform.pk),
        })
        self.assertContains(combined, self.cd.name)
        self.assertNotContains(combined, self.tech.name)
        self.assertContains(combined, 'value="A1"', html=False)
        tech_combined = self.client.get(url, {
            "search": "Приставка",
            "location": "B3",
            "brand": str(self.brand.pk),
            "product_type": str(self.product_type.pk),
        })
        self.assertContains(tech_combined, self.tech.name)
        self.assertNotContains(tech_combined, self.cd.name)

    def test_global_stock_and_nomenclature_have_no_location_column(self):
        self.assign("A1-2")
        self.client.force_login(self.actor)
        global_response = self.client.get(reverse("warehouse:global_stock"))
        nomenclature_response = self.client.get(reverse("nomenclature:list"))
        self.assertNotContains(global_response, "Место хранения")
        self.assertNotContains(nomenclature_response, "Место хранения")

    def test_warehouse_page_location_loading_does_not_add_n_plus_one_queries(self):
        self.assign("A1-1")
        self.client.force_login(self.actor)
        url = reverse("warehouse:detail", args=(self.warehouse.pk,))
        with CaptureQueriesContext(connection) as initial_queries:
            self.assertEqual(self.client.get(url).status_code, 200)

        for index in range(5):
            product = CD.objects.create(
                platform=self.platform,
                name=f"Игра {index}",
                sku=f"CD-N-{index}",
                barcode=f"N-{index}",
                retail_price=100,
                cost=100,
            )
            CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=product, quantity=1)
            self.assign(f"C{index + 1}-1", product=product)

        with CaptureQueriesContext(connection) as expanded_queries:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertLessEqual(len(expanded_queries), len(initial_queries))

    def test_sale_last_unit_clears_only_source_and_new_supply_does_not_restore(self):
        self.cd_stock.quantity = 1
        self.cd_stock.save(update_fields=("quantity",))
        self.assign("A1-2")
        self.assign("B1-1", warehouse=self.other_warehouse)
        sale = create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
            lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 1}],
        )
        self.assertTrue(sale.pk)
        self.assertFalse(self.cd_stock.storage_assignments.exists())
        self.assertTrue(self.other_cd_stock.storage_assignments.exists())
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Тест возврата")
        self.cd_stock.refresh_from_db()
        self.assertEqual(self.cd_stock.quantity, 1)
        self.assertFalse(self.cd_stock.storage_assignments.exists())
        supplier = Supplier.objects.create(
            name="Поставщик", letter="S", highlight_color="#123456",
            legal_entity="ООО", phone_1="1",
        )
        accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[{
                "product_type": "cd", "product_id": self.cd.pk, "supplier_id": supplier.pk,
                "quantity": 5, "purchase_unit_cost": "100",
            }],
        )
        self.assertFalse(self.cd_stock.storage_assignments.exists())

    def test_transfer_and_consignment_clear_source_at_zero_without_destination_location(self):
        self.cd_stock.quantity = 1
        self.cd_stock.save(update_fields=("quantity",))
        self.assign("A1-2")
        transfer = create_transfer(
            actor=self.actor,
            source_warehouse_id=self.warehouse.pk,
            destination_warehouse_id=self.other_warehouse.pk,
            lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 1}],
        )
        self.assertFalse(self.cd_stock.storage_assignments.exists())
        advance_transfer_status(actor=self.actor, transfer_id=transfer.pk, next_status="assembled")
        advance_transfer_status(actor=self.actor, transfer_id=transfer.pk, next_status="shipped")
        advance_transfer_status(actor=self.actor, transfer_id=transfer.pk, next_status="accepted")
        self.assertEqual(self.other_cd_stock.storage_assignments.count(), 0)

        self.tech_stock.quantity = 1
        self.tech_stock.save(update_fields=("quantity",))
        self.assign("C1-1", product_type="tech")
        shop = SalesPlatform.objects.create(
            name="Площадка", address="Адрес", legal_entity="ООО", phone_1="1",
        )
        transfer_to_consignment(
            actor=self.actor, warehouse_id=self.warehouse.pk, platform_id=shop.pk,
            product_type="tech", product_id=self.tech.pk, quantity=1, receivable_per_unit="250",
        )
        self.assertFalse(self.tech_stock.storage_assignments.exists())

    def test_supply_cancellation_to_zero_clears_location(self):
        zero_stock_product = CD.objects.create(
            platform=self.platform, name="Товар прихода", sku="CD-SUPPLY", barcode="3", cost=0,
        )
        stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=zero_stock_product, quantity=0)
        supplier = Supplier.objects.create(
            name="Поставщик 2", letter="P", highlight_color="#654321",
            legal_entity="ООО", phone_1="1",
        )
        supply = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[{
                "product_type": "cd", "product_id": zero_stock_product.pk, "supplier_id": supplier.pk,
                "quantity": 2, "purchase_unit_cost": "100",
            }],
        )
        update_storage_locations(
            actor=self.actor, warehouse_id=self.warehouse.pk, product_type="cd",
            product_id=zero_stock_product.pk, raw_value="D1-1",
        )
        cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка прихода")
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 0)
        self.assertFalse(stock.storage_assignments.exists())

    def test_cleanup_audit_failure_rolls_back_stock_operation(self):
        self.cd_stock.quantity = 1
        self.cd_stock.save(update_fields=("quantity",))
        self.assign("A1-2")
        with patch("warehouse.storage_services.record_product_changes", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                create_sale(
                    actor=self.actor, warehouse_id=self.warehouse.pk,
                    price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
                    payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                    lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 1}],
                )
        self.cd_stock.refresh_from_db()
        self.assertEqual(self.cd_stock.quantity, 1)
        self.assertTrue(self.cd_stock.storage_assignments.exists())
        self.assertEqual(Sale.objects.count(), 0)
