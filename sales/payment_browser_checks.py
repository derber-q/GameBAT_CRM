"""Проверка оплаты в Chromium с отдельной тестовой БД и снимками интерфейса."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from cash.models import CashTransaction
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale


def database_call(callback, *args):
    try:
        return callback(*args)
    finally:
        connections.close_all()


class PaymentBrowserChecks(StaticLiveServerTestCase):
    def test_bank_creation_defaults_payment_dialog_and_completion(self):
        actor = User.objects.create_superuser("payment-browser", password="IsolatedTest123!")
        self.client.force_login(actor)
        warehouse = Warehouse.objects.create(name="Склад проверки оплаты")
        product = CD.objects.create(
            platform=Platform.objects.create(name="PS5"), name="Игра для проверки оплаты",
            sku="PAY-BROWSER", barcode="000000012345", avito_price=10000, cost=8000,
        )
        stock = CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        output = Path(settings.BASE_DIR) / "outputs" / "payment-browser"
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1280, 390):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                                     "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                                     "url": self.live_server_url}])
                context.route("**/crm/api/exchange-rates/", lambda route: route.fulfill(json={"rates": {}, "available": False}))
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("sales:create"))
                page.locator("#id_warehouse").select_option(str(warehouse.pk))
                expect(page.locator("#id_payment_method option")).to_have_count(4)
                for channel in ("avito", "yandex_market"):
                    page.locator("#id_sale_type").select_option(channel)
                    expect(page.locator("#id_payment_method")).to_have_value("bank_transfer_postpay")
                    expect(page.locator("#id_cash_received_amount")).to_be_hidden()
                page.locator("#id_sale_type").select_option("retail")
                page.locator("#id_payment_method").select_option("bank_account")
                expect(page.locator("#id_cash_received_amount")).to_be_visible()
                page.locator("[data-sale-barcode-input]").fill("000000012345")
                page.locator("[data-sale-barcode-input]").press("Enter")
                expect(page.locator('[name="product_id"]')).to_have_value(str(product.pk))
                page.locator("#id_cash_received_amount").fill("10500")
                page.screenshot(path=str(output / f"bank-create-{width}.png"), full_page=True)
                page.get_by_role("button", name="Продажа выполнена", exact=True).click()
                page.wait_for_url("**/sales/*/")
                immediate = database.submit(database_call, Sale.objects.latest, "pk").result()
                self.assertTrue(immediate.is_completed)
                self.assertEqual(immediate.extra_cash_amount, 500)
                page.screenshot(path=str(output / f"bank-detail-{width}.png"), full_page=True)

                page.goto(self.live_server_url + reverse("sales:create"))
                page.locator("#id_warehouse").select_option(str(warehouse.pk))
                page.locator("#id_sale_type").select_option("avito")
                page.locator("[data-sale-barcode-input]").fill("000000012345")
                page.locator("[data-sale-barcode-input]").press("Enter")
                expect(page.locator('[name="product_id"]')).to_have_value(str(product.pk))
                page.get_by_role("button", name="Продажа выполнена", exact=True).click()
                page.wait_for_url("**/sales/*/")
                deferred = database.submit(database_call, Sale.objects.latest, "pk").result()
                self.assertEqual(deferred.payment_status, "unpaid")
                self.assertIsNone(deferred.cash_received_amount)
                expect(page.locator('[name="cash_received_amount"]')).to_be_visible()
                page.goto(self.live_server_url + reverse("sales:incomplete"))
                row = page.locator(f'[data-sale-row="{deferred.pk}"]')
                row.locator('[data-status-field="payment"]').select_option("paid")
                dialog = page.locator("#sale-status-dialog")
                expect(dialog).to_be_visible()
                expect(dialog.locator("#sale-status-cash")).to_be_visible()
                dialog.locator("#sale-status-cash").fill("10500")
                page.screenshot(path=str(output / f"bank-postpay-dialog-{width}.png"), full_page=True)
                dialog.get_by_role("button", name="Подтвердить", exact=True).click()
                expect(row.locator(".sale-status-paid")).to_be_visible()
                expect(row.locator('option[value="shipped"]')).to_have_count(0)
                for status in ("assembled", "delivered"):
                    row.locator('[data-status-field="order"]').select_option(status)
                    dialog.get_by_role("button", name="Подтвердить", exact=True).click()
                    if status != "delivered":
                        expect(row.locator('[data-status-field="order"]')).to_have_value(status)
                        expect(row.locator('[data-status-field="order"] option')).to_have_text(['Собран', 'Доставлен'])
                        row.locator('[data-status-field="order"]').scroll_into_view_if_needed()
                        page.screenshot(path=str(output / f"assembled-direct-delivery-{width}.png"), full_page=True)
                expect(row).to_have_count(0)
                database.submit(database_call, deferred.refresh_from_db).result()
                self.assertTrue(deferred.is_completed)
                self.assertEqual(deferred.extra_cash_amount, 500)
                self.assertEqual(deferred.paid_by_id, actor.pk)
                self.assertEqual(errors, [])
                context.close()
            browser.close()
        warehouse.cash_register.refresh_from_db()
        warehouse.safe.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual((warehouse.cash_register.balance, warehouse.safe.balance), (0, 0))
        self.assertFalse(CashTransaction.objects.exists())
        self.assertEqual(stock.quantity, 6)
