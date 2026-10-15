"""Реальный браузер и отдельная тестовая БД, без рабочих продаж и интеграций."""
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import BarcodeRegistry, CD, Platform
from catalog.system_products import ensure_system_products
from cash.models import CashTransaction
from warehouse.models import CDWarehouseStock, CDWarehouseStorageAssignment, Warehouse, WarehouseStorageLocation

from .models import Sale
from .services import create_sale


class SystemProductsBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        ensure_system_products()
        self.user = User.objects.create_superuser("system-browser", password="StrongAdmin!123")
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(name="Браузер — основной склад")
        self.other = Warehouse.objects.create(name="Браузер — второй склад")
        self.empty = Warehouse.objects.create(name="Браузер — пустой склад")
        self.cd = CD.objects.create(platform=Platform.objects.create(name="PS5 браузер"), name="Игра для проверки мест хранения", sku="BROWSER-SYSTEM-CD", barcode="000011112222", weight_grams=140, cost=100, avito_price=500)
        stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=5)
        CDWarehouseStock.objects.create(warehouse=self.other, cd=self.cd, quantity=12)
        for index, (rack, shelf, columns) in enumerate(((1, 2, [1, 2]), (6, 3, []))):
            location = WarehouseStorageLocation.objects.create(warehouse=self.warehouse, room="A", rack=rack, shelf=shelf, columns=columns)
            CDWarehouseStorageAssignment.objects.create(stock=stock, location=location, position=index)
        self.output = Path(settings.BASE_DIR) / "outputs" / "system-products-browser"
        self.output.mkdir(parents=True, exist_ok=True)

    def context(self, browser, width):
        context = browser.new_context(viewport={"width": width, "height": 900}, is_mobile=width < 600, has_touch=width < 600)
        context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}])
        context.route("**/crm/api/exchange-rates/", lambda route: route.fulfill(json={"rates": {}, "available": False}))
        return context

    def test_statistics_and_supply_desktop_and_mobile(self):
        create_sale(actor=self.user, warehouse_id=self.warehouse.pk, price_type="retail", sale_type="retail", payment_method="cash", lines=[{"product_type": "system", "system_kind": "DIGITAL_PRODUCT", "unit_cost": "3000", "unit_price": "4500", "quantity": 1}], note="Браузерная проверка")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1280, 390):
                context = self.context(browser, width)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("statistics:index"))
                targets = ("stats-report-filters", "stats-dynamics", "stats-channels")
                for target in targets:
                    expect(page.locator(f"#{target}")).to_be_hidden()
                page.locator('[aria-controls="stats-report-filters"]').click()
                expect(page.locator("#stats-report-filters")).to_be_visible()
                expect(page.locator("#stats-dynamics")).to_be_hidden()
                page.locator('[aria-controls="stats-dynamics"]').click()
                expect(page.locator("#stats-dynamics svg")).to_be_visible()
                page.locator('[aria-controls="stats-dynamics"]').click()
                expect(page.locator("#stats-dynamics")).to_be_hidden()
                page.locator('[aria-controls="stats-channels"]').click()
                expect(page.locator("#stats-channels table")).to_be_visible()
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(self.output / f"statistics-open-{width}.png"), full_page=True)
                page.reload()
                for target in targets:
                    expect(page.locator(f"#{target}")).to_be_hidden()
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(self.output / f"statistics-closed-{width}.png"), full_page=True)
                page.locator('[aria-controls="stats-report-filters"]').click()
                page.locator("#id_operation_kind").select_option("DIGITAL_PRODUCT")
                page.get_by_role("button", name="Сформировать отчёт").click()
                expect(page.locator("#id_operation_kind")).to_have_value("DIGITAL_PRODUCT")
                expect(page.locator("#stats-report-filters")).to_be_hidden()
                page.goto(self.live_server_url + reverse("supplies:create"))
                page.locator("#id_warehouse").select_option(str(self.warehouse.pk))
                page.locator('[name="product_search"]').first.fill("000011112222")
                reference = page.locator("[data-supply-stock-reference]").first
                expect(reference).to_have_text("На складе: 5 шт. (A1-2-1\\2, A6-3)")
                page.locator('[name="quantity"]').first.fill("7")
                page.locator('[name="purchase_unit_cost"]').first.fill("123.45")
                page.locator("#id_warehouse").select_option(str(self.other.pk))
                expect(reference).to_have_text("На складе: 12 шт. (место не указано)")
                page.locator("#id_warehouse").select_option(str(self.empty.pk))
                expect(reference).to_have_text("На складе: 0 шт. (место не указано)")
                expect(page.locator('[name="quantity"]').first).to_have_value("7")
                expect(page.locator('[name="purchase_unit_cost"]').first).to_have_value("123.45")
                expect(page.locator("#supply-lines tr").first.locator("td")).to_have_count(5)
                page.locator("#id_warehouse").select_option(str(self.warehouse.pk))
                expect(reference).to_have_text("На складе: 5 шт. (A1-2-1\\2, A6-3)")
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(self.output / f"supply-{width}.png"), full_page=True)
                self.assertEqual(errors, [])
                context.close()
            browser.close()

    def test_scan_create_system_operations_in_browser(self):
        codes = dict(BarcodeRegistry.objects.filter(system_product__isnull=False).values_list("system_product_id", "value"))
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1280, 390):
                context = self.context(browser, width)
                page = context.new_page()
                page.goto(self.live_server_url + reverse("sales:create"))
                page.locator("#id_warehouse").select_option(str(self.warehouse.pk))
                barcode = page.locator("[data-sale-barcode-input]")
                barcode.fill(codes["DIGITAL_PRODUCT"])
                barcode.press("Enter")
                expect(page.locator(".sale-custom-line")).to_have_count(1)
                expect(page.locator('[name="note"]')).to_have_attribute("required", "")
                page.locator('[name="custom_unit_cost"]').fill("3000")
                page.locator('[name="custom_unit_price"]').fill("4500")
                barcode.fill(codes["DIGITAL_PRODUCT"]); barcode.press("Enter")
                expect(page.locator(".sale-custom-line")).to_have_count(2)
                expect(page.locator('[name="custom_unit_cost"]').first).to_have_value("3000")
                page.locator('[name="custom_unit_cost"]').nth(1).fill("2000")
                page.locator('[name="custom_unit_price"]').nth(1).fill("2500")
                barcode.fill(codes["EXPENSE"]); barcode.press("Enter")
                expect(page.locator("[data-sale-barcode-feedback]")).to_contain_text("отдельной продажей")
                expect(page.locator(".sale-custom-line")).to_have_count(2)
                page.locator('[name="note"]').fill("Два цифровых товара")
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(self.output / f"digital-{width}.png"), full_page=True)
                page.get_by_role("button", name="Продажа выполнена").click()
                page.wait_for_url("**/crm/sales/*/")
                expect(page.locator("h1")).to_contain_text("SALE-")
                page.goto(self.live_server_url + reverse("sales:create"))
                page.locator("#id_warehouse").select_option(str(self.warehouse.pk))
                barcode = page.locator("[data-sale-barcode-input]")
                barcode.fill(codes["EXPENSE"]); barcode.press("Enter")
                expect(page.locator('[name="custom_unit_price"]')).to_have_value("0")
                expect(page.locator('[name="custom_unit_price"]')).to_have_attribute("readonly", "")
                page.locator('[name="custom_unit_cost"]').fill("2500")
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(self.output / f"expense-{width}.png"), full_page=True)
                page.get_by_role("button", name="Продажа выполнена").click()
                page.wait_for_url("**/crm/sales/*/")
                expect(page.locator("h1")).to_contain_text("SALE-")
                context.unroute_all(behavior="wait")
                context.close()
            browser.close()
        self.assertEqual(Sale.objects.filter(operation_kind="DIGITAL_PRODUCT", total_amount=7000).count(), 2)
        expenses = Sale.objects.filter(operation_kind="EXPENSE")
        self.assertEqual(expenses.count(), 2)
        self.assertTrue(all(expense.total_amount == 0 for expense in expenses))
        self.assertFalse(CashTransaction.objects.filter(sale__in=expenses).exists())
