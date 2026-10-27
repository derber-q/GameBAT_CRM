"""Выбор оптовой цены и сохранение продажи в изолированном Chromium."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale, SaleCDItem
from .payment_browser_checks import database_call


class SalePriceTypeBrowserChecks(StaticLiveServerTestCase):
    def test_wholesale_choice_reprices_scanned_items_and_saves_wholesale_sale(self):
        actor = User.objects.create_superuser("wholesale-price-browser")
        self.client.force_login(actor)
        warehouse = Warehouse.objects.create(name="Склад проверки оптовой цены")
        product = CD.objects.create(name="Игра для проверки опта", platform=Platform.objects.create(name="PS5"),
            barcode="000000023456", avito_price=10000, wholesale_price=9000, yandex_market_price=11000, cost=8000)
        CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        output = Path(settings.BASE_DIR) / "outputs/sale_wholesale_price_20261022/browser"
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            for width in (1440, 390):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}])
                context.route("**/crm/api/exchange-rates/", lambda route: route.fulfill(json={"rates": {}, "available": False}))
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("sales:create"))
                page.locator("#id_warehouse").select_option(str(warehouse.pk))
                price = page.locator("#id_price_type")
                channel = page.locator("#id_sale_type")
                wholesale = price.locator('option[value="wholesale"]')
                expect(wholesale).to_be_disabled()
                barcode = page.locator("[data-sale-barcode-input]")
                barcode.fill("000000023456")
                barcode.press("Enter")
                expect(page.locator('[name="product_id"]')).to_have_value(str(product.pk))
                expect(page.locator("[data-sale-intermediate-total]")).to_have_text("10 000,00 ₽")
                for destination, expected_price in [("retail", "retail"), ("avito", "retail")]:
                    channel.select_option("wholesale")
                    expect(price).to_have_value("wholesale")
                    expect(wholesale).to_be_enabled()
                    expect(page.locator("[data-sale-intermediate-total]")).to_have_text("9 000,00 ₽")
                    channel.select_option(destination)
                    expect(price).to_have_value(expected_price)
                    expect(wholesale).to_be_disabled()
                    self.assertTrue(wholesale.evaluate("option => option.hidden"))
                channel.select_option("wholesale")
                barcode.fill("000000023456")
                barcode.press("Enter")
                expect(page.locator('[name="quantity"]')).to_have_value("2")
                expect(page.locator("[data-sale-intermediate-total]")).to_have_text("18 000,00 ₽")
                page.locator("#id_payment_method").select_option("bank_account")
                page.locator('#id_customer').select_option('custom')
                page.locator('#id_custom_partner_name').fill('Тестовый заказчик')
                page.screenshot(path=str(output / f"wholesale-{width}.png"), full_page=True)
                page.get_by_role("button", name="Продажа выполнена", exact=True).click()
                page.wait_for_url("**/sales/*/")
                sale = run(lambda: Sale.objects.latest("pk"))
                item = run(lambda: SaleCDItem.objects.get(sale=sale))
                self.assertEqual((sale.sale_type, sale.price_type), ("wholesale", "wholesale"))
                self.assertEqual((item.quantity, item.unit_price, sale.total_amount), (2, 9000, 18000))
                self.assertEqual(errors, [])
                context.close()
            browser.close()
