"""Системные операции: штрихкоды, снимки, касса, склад, отчёт и запреты backend."""
import uuid
from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import User
from catalog.models import BarcodeRegistry, CD, Platform, SystemProduct
from catalog.system_products import ensure_system_products
from cash.models import CashTransaction
from warehouse.models import CDWarehouseStock, CDWarehouseStorageAssignment, Warehouse, WarehouseStorageLocation

from .models import Sale
from .services import advance_order_status, cancel_sale, create_sale, edit_postpay_sale_items, mark_sale_paid, update_sale_note
from .statistics_excel import render_statistics_workbook
from .statistics_service import build_sales_statistics_report


class SystemProductTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_system_products()
        cls.user = User.objects.create_superuser("system-admin", password="StrongAdmin!123")
        cls.warehouse = Warehouse.objects.create(name="Склад системных операций")
        cls.other = Warehouse.objects.create(name="Другой склад системных операций")
        cls.cd = CD.objects.create(platform=Platform.objects.create(name="SYSTEM-PS5"), name="Обычная игра", sku="SYS-CD", cost=100, avito_price=500, weight_grams=140)
        cls.stock = CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=cls.cd, quantity=5)
        CDWarehouseStock.objects.create(warehouse=cls.other, cd=cls.cd, quantity=12)
        for index, values in enumerate((("A", 1, 2, [1, 2]), ("A", 6, 3, []))):
            room, rack, shelf, columns = values
            location = WarehouseStorageLocation.objects.create(warehouse=cls.warehouse, room=room, rack=rack, shelf=shelf, columns=columns)
            CDWarehouseStorageAssignment.objects.create(stock=cls.stock, location=location, position=index)

    def setUp(self):
        self.client.force_login(self.user)

    def line(self, kind="DIGITAL_PRODUCT", cost="3000", price="4500", quantity=1):
        return {"product_type": "system", "system_kind": kind, "unit_cost": cost, "unit_price": price, "quantity": quantity}

    def sale(self, lines=None, **kwargs):
        values = dict(actor=self.user, warehouse_id=self.warehouse.pk, price_type="retail", sale_type="retail", payment_method="cash", lines=lines or [self.line()], note="Подписка покупателя")
        values.update(kwargs)
        return create_sale(**values)

    def test_exactly_two_stable_globally_unique_barcodes_and_protected_cards(self):
        before = dict(BarcodeRegistry.objects.filter(system_product__isnull=False).values_list("system_product_id", "value"))
        ensure_system_products()
        ensure_system_products()
        self.assertEqual(set(before), {"DIGITAL_PRODUCT", "EXPENSE"})
        self.assertEqual(SystemProduct.objects.count(), 2)
        self.assertEqual(before, dict(BarcodeRegistry.objects.filter(system_product__isnull=False).values_list("system_product_id", "value")))
        self.assertEqual(len(set(before.values())), 2)
        for kind, code in before.items():
            entry = BarcodeRegistry.objects.get(value=code)
            self.assertEqual(entry.product.kind, kind)
            entry.value = "replacement"
            with self.assertRaises(ValidationError):
                entry.save()
            with self.assertRaises(ValidationError):
                entry.delete()
            with self.assertRaises(ValidationError):
                entry.system_product.delete()
            response = self.client.get(reverse("admin:catalog_systemproduct_change", args=[kind]))
            self.assertContains(response, code)

    def test_scan_finds_system_without_stock_and_supply_does_not_find_it(self):
        code = BarcodeRegistry.objects.get(system_product_id="DIGITAL_PRODUCT").value
        response = self.client.get(reverse("supplies:autocomplete"), {"q": code, "warehouse": self.warehouse.pk, "context": "sale"})
        result = response.json()["results"][0]
        self.assertEqual((result["type"], result["system_kind"], result["barcode"]), ("system", "DIGITAL_PRODUCT", code))
        for context in ("supply", "transfer", "consignment"):
            self.assertEqual(self.client.get(reverse("supplies:autocomplete"), {"q": code, "warehouse": self.warehouse.pk, "context": context}).json()["results"], [])

    def test_digital_multiple_independent_snapshots_and_no_inventory_changes(self):
        sale = self.sale([self.line(), self.line(cost="2000", price="2500", quantity=2)])
        items = list(sale.custom_items.order_by("pk"))
        self.assertEqual([(item.unit_cost_snapshot, item.unit_price) for item in items], [(Decimal("3000"), Decimal("4500")), (Decimal("2000"), Decimal("2500"))])
        report = build_sales_statistics_report({})
        self.assertEqual((report.totals.actual_revenue, report.totals.cost, report.totals.profit), (Decimal("9500"), Decimal("7000"), Decimal("2500")))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.assertEqual(CDWarehouseStorageAssignment.objects.filter(stock=self.stock).count(), 2)
        self.sale([self.line(cost="1", price="100")])
        items[0].refresh_from_db()
        self.assertEqual(items[0].unit_cost_snapshot, Decimal("3000"))
        items[0].unit_price = 1
        with self.assertRaises(ValidationError):
            items[0].save()

    def test_digital_note_required_on_create_edit_and_note_update(self):
        for note in ("", "   ", "\n\t"):
            with self.assertRaisesMessage(ValidationError, "Для продажи цифрового товара"):
                self.sale(note=note)
        sale = self.sale(payment_method="cash_postpay")
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[self.line()], note=" ")
        with self.assertRaises(ValidationError):
            update_sale_note(actor=self.user, sale_id=sale.pk, note=" ")

    def test_expenses_zero_revenue_negative_profit_without_any_cash_or_stock_movement(self):
        sale = self.sale([self.line("EXPENSE", "1500", "0"), self.line("EXPENSE", "700", "0"), self.line("EXPENSE", "300", "0")], sale_type="avito", note="Расходы магазина")
        self.assertEqual(sale.total_amount, 0)
        self.assertTrue(sale.is_completed)
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())
        report = build_sales_statistics_report({})
        self.assertEqual((report.totals.actual_revenue, report.totals.cost, report.totals.profit), (Decimal("0"), Decimal("2500"), Decimal("-2500")))
        self.assertEqual((report.totals.sales_count, report.totals.expenses_count, report.totals.units), (0, 1, 0))
        self.assertIsNone(report.totals.margin)
        self.assertIsNone(report.totals.average_check)
        self.assertEqual(report.channels[0].key, "expense")
        self.assertEqual(report.totals.commission, 0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)

    def test_expense_price_adjustment_and_extra_cash_cannot_be_forged(self):
        for line in (self.line("EXPENSE", price="1"), dict(self.line("EXPENSE", price="0"), unit_discount="-1")):
            with self.assertRaises(ValidationError):
                self.sale([line])
        with self.assertRaises(ValidationError):
            self.sale([self.line("EXPENSE", price="0")], cash_received_amount="1")
        self.assertFalse(Sale.objects.exists())

    def test_system_money_and_quantity_are_required_finite_and_nonnegative(self):
        for values in ({"cost": ""}, {"cost": "-1"}, {"cost": "NaN"}, {"price": "Infinity"}, {"price": "-1"}, {"quantity": "0"}, {"quantity": "1.5"}, {"cost": "1000000000000000000"}, {"price": "999999999999999999", "quantity": "2147483647"}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.sale([self.line(**values)])
        with self.assertRaises(ValidationError):
            self.sale([{"product_type": "unknown", "quantity": 1}])
        self.assertFalse(Sale.objects.exists())

    def test_all_mixed_modes_rejected_in_both_orders_and_in_edit(self):
        normal_lines = [
            {"product_type": "cd", "product_id": self.cd.pk, "quantity": 1},
            {"product_type": "tech", "product_id": 99999, "quantity": 1},
            {"product_type": "custom", "name": "Услуга", "unit_price": "100", "unit_cost": "10", "quantity": 1},
            {"product_type": "consignment", "product_kind": "cd", "stock_id": 99999, "quantity": 1},
        ]
        for kind in ("DIGITAL_PRODUCT", "EXPENSE"):
            special = self.line(kind, price="0" if kind == "EXPENSE" else "4500")
            for other in normal_lines + [self.line("EXPENSE" if kind == "DIGITAL_PRODUCT" else "DIGITAL_PRODUCT", price="0")]:
                for lines in ([special, other], [other, special]):
                    with self.subTest(kind=kind, other=other["product_type"], lines=lines), self.assertRaisesMessage(ValidationError, "отдельной продажей"):
                        self.sale(lines)
        sale = self.sale(payment_method="cash_postpay")
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[self.line(), normal_lines[0]])
        self.assertEqual(sale.custom_items.count(), 1)

    def test_expense_deferred_completion_cancellation_and_no_refund_or_stock_return(self):
        sale = self.sale([self.line("EXPENSE", price="0")], payment_method="cash_postpay")
        self.assertEqual(build_sales_statistics_report({}).totals.profit, 0)
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        for status in ("assembled", "shipped", "delivered"):
            advance_order_status(actor=self.user, sale_id=sale.pk, next_status=status)
        self.assertEqual(build_sales_statistics_report({}).totals.profit, Decimal("-3000"))
        result = cancel_sale(actor=self.user, sale_id=sale.pk, comment="Отмена расхода")
        self.assertIsNone(result.refund_transaction)
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())
        self.assertEqual(build_sales_statistics_report({}).totals.profit, 0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.assertFalse(cancel_sale(actor=self.user, sale_id=sale.pk, comment="Повтор").cancelled)

    def test_digital_cash_cancel_refunds_payment_once_without_creating_stock(self):
        sale = self.sale()
        self.assertEqual(sale.cash_transactions.count(), 1)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment="Возврат цифрового товара")
        self.assertEqual(sale.cash_transactions.count(), 2)
        self.assertEqual(build_sales_statistics_report({}).totals.sales_count, 0)
        self.assertEqual(CDWarehouseStock.objects.get(pk=self.stock.pk).quantity, 5)

    def test_edit_manual_values_and_replace_all_rows_with_another_mode(self):
        sale = self.sale(payment_method="cash_postpay")
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[self.line(cost="3100", price="4600", quantity=2)], note="Изменённый цифровой товар")
        item = sale.custom_items.get()
        self.assertEqual((item.unit_cost_snapshot, item.unit_price, item.quantity), (Decimal("3100"), Decimal("4600"), 2))
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[self.line("EXPENSE", "500", "0")])
        sale.refresh_from_db()
        self.assertEqual((sale.operation_kind, sale.total_amount), ("EXPENSE", 0))
        self.assertEqual(sale.custom_items.get().unit_cost_snapshot, Decimal("500"))
        self.assertEqual(CDWarehouseStock.objects.get(pk=self.stock.pk).quantity, 5)

    def test_expenses_do_not_change_average_check_and_excel_matches_same_report(self):
        self.sale([self.line(cost="1000", price="1500")])
        self.sale([self.line("EXPENSE", "500", "0")])
        report = build_sales_statistics_report({})
        self.assertEqual((report.totals.profit, report.totals.average_check), (Decimal("0"), Decimal("1500")))
        workbook = load_workbook(BytesIO(render_statistics_workbook(report)), data_only=True)
        summary = dict(workbook["Сводка"].values)
        self.assertEqual(summary["Чистая прибыль"], 0)
        self.assertEqual(summary["Операций расхода"], 1)
        self.assertEqual(len(list(workbook["Позиции продаж"].values)), 3)
        with CaptureQueriesContext(connection) as queries:
            build_sales_statistics_report({})
        self.assertLessEqual(len(queries), 7)
        self.assertEqual(build_sales_statistics_report({"operation_kind": "EXPENSE"}).totals.profit, Decimal("-500"))
        self.assertEqual(build_sales_statistics_report({"channels": ["expense"]}).totals.expenses_count, 1)
        self.assertEqual(build_sales_statistics_report({"channels": ["retail"]}).totals.expenses_count, 0)

    def test_idempotent_create_returns_same_sale_and_rejects_changed_payload(self):
        key = uuid.uuid4()
        sale = self.sale(creation_key=key)
        self.assertEqual(self.sale(creation_key=key).pk, sale.pk)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(sale.cash_transactions.count(), 1)
        with self.assertRaises(ValidationError):
            self.sale([self.line(price="999")], creation_key=key)

    def test_previous_sale_schema_remains_compatible_with_running_workers(self):
        from django.db.migrations.executor import MigrationExecutor
        apps = MigrationExecutor(connection).loader.project_state([("sales", "0018_signed_unit_discount")]).apps
        old_sale = apps.get_model("sales", "Sale").objects.create(
            warehouse_id=self.warehouse.pk, price_type="retail", sale_type="retail", payment_method="bank_account",
        )
        current = Sale.objects.get(pk=old_sale.pk)
        self.assertEqual(current.operation_kind, "normal")
        self.assertEqual(current.creation_fingerprint, "")

    def test_post_validates_mixing_expense_price_and_note_and_preserves_csrf(self):
        payload = {"warehouse": self.warehouse.pk, "price_type": "retail", "sale_type": "retail", "payment_method": "cash", "custom_name": ["Расход"], "custom_quantity": ["1"], "custom_unit_cost": ["100"], "custom_unit_price": ["10"], "custom_system_kind": ["EXPENSE"]}
        response = self.client.post(reverse("sales:create"), payload)
        self.assertContains(response, "Цена расхода всегда")
        self.assertFalse(Sale.objects.exists())
        payload["custom_system_kind"] = ["DIGITAL_PRODUCT"]
        self.assertContains(self.client.post(reverse("sales:create"), payload), "Для продажи цифрового товара")
        payload.update(note="Описание", creation_key=str(uuid.uuid4()))
        self.assertEqual(self.client.post(reverse("sales:create"), payload).status_code, 302)
        self.assertEqual(self.client.post(reverse("sales:create"), payload).status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse("sales:create"), payload).status_code, 403)

    def test_create_and_autocomplete_require_existing_permissions(self):
        user = User.objects.create_user("system-no-permissions", password="StrongAdmin!123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("sales:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("supplies:autocomplete"), {"context": "sale", "q": "Расход"}).status_code, 403)

    def test_statistics_all_three_sections_start_collapsed_even_with_active_filters(self):
        response = self.client.get(reverse("statistics:index"), {"operation_kind": "EXPENSE"})
        for target in ("stats-report-filters", "stats-dynamics", "stats-channels"):
            self.assertContains(response, f'aria-expanded="false" aria-controls="{target}"')
            self.assertContains(response, f'id="{target}" class="collapsible-content" hidden')

    def test_supply_reference_uses_selected_stock_all_locations_and_zero_stock(self):
        url = reverse("supplies:autocomplete")
        for warehouse, expected, locations in ((self.warehouse, 5, "A1-2-1\\2, A6-3"), (self.other, 12, "")):
            result = self.client.get(url, {"context": "supply", "warehouse": warehouse.pk, "items": f"cd:{self.cd.pk}"}).json()["results"][0]
            self.assertEqual((result["warehouse_stock"], result["storage_locations"]), (expected, locations))
        empty = Warehouse.objects.create(name="Пустой склад")
        result = self.client.get(url, {"context": "supply", "warehouse": empty.pk, "items": f"cd:{self.cd.pk}"}).json()["results"][0]
        self.assertEqual((result["warehouse_stock"], result["storage_locations"]), (0, ""))
