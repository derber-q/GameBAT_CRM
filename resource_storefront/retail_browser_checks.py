"""Розничный путь покупателя в отдельной SQLite; оплата в тесте задаётся явно."""
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright, expect
from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from sales.models import Sale
from cash.models import CashTransaction
from .models import RetailSettings
from .retail_security import retail_link
from .security import recover_token

@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class RetailBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        warehouse=Warehouse.objects.create(name="Розничный браузерный тест")
        RetailSettings.objects.update_or_create(pk=1,defaults={"warehouse":warehouse})
        self.token=recover_token(retail_link())
        platform=Platform.objects.create(name="Nintendo Switch 2")
        with sqlite3.connect(f"file:{Path(settings.BASE_DIR)/'db.sqlite3'}?mode=ro",uri=True) as db:
            samples=db.execute("SELECT name,title_image FROM catalog_cd WHERE title_image!='' ORDER BY id LIMIT 14").fetchall()
        self.products=[]
        for index,(name,photo) in enumerate(samples):
            product=CD.objects.create(name=name,platform=platform,title_image=photo if index else "",avito_price=4500+index,wholesale_price=1234,cost=500)
            CDWarehouseStock.objects.create(warehouse=warehouse,cd=product,quantity=30)
            self.products.append(product)

    def test_retail_journey(self):
        output=Path(settings.BASE_DIR)/"outputs"/"resource-retail"
        output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            for engine in ("chromium","webkit"):
                browser=getattr(pw,engine).launch()
                context=browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
                page=context.new_page()
                errors=[]
                page.on("pageerror",lambda err:errors.append(str(err)))
                page.goto(self.live_server_url+"/retailer/"+self.token+"/",wait_until="networkidle")
                self.assertTrue(page.url.endswith("/retailer/"))
                self.assertNotIn("/opt/",page.locator("body").inner_html())
                for width in (360,390,430,768,1440):
                    page.set_viewport_size({"width":width,"height":844 if width<700 else 1000})
                    page.goto(self.live_server_url+"/retailer/catalog/",wait_until="networkidle")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),width)
                    page.screenshot(path=str(output/f"{engine}-catalog-{width}.png"),full_page=True)
                page.set_viewport_size({"width":390,"height":844})
                page.locator(".rs-filter-open").click()
                page.locator("#id_category").select_option("cd")
                page.locator("#id_price_min").fill("4500")
                page.locator("#rs-catalog-form [type=submit]").click()
                page.wait_for_load_state("networkidle")
                page.locator(".rs-card-image").nth(1).click()
                page.wait_for_load_state("networkidle")
                for width in (360,390,430,768,1440):
                    page.set_viewport_size({"width":width,"height":844 if width<700 else 1000})
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),width)
                    page.screenshot(path=str(output/f"{engine}-product-{width}.png"),full_page=True)
                page.set_viewport_size({"width":390,"height":844})
                page.locator(".rs-buy-detail [name=quantity]").fill("2")
                page.locator(".rs-buy-detail [type=submit]").click()
                expect(page.locator(".rs-toast")).to_contain_text("Добавлено")
                page.locator(".rs-mobile-cart").click()
                page.wait_for_load_state("networkidle")
                page.locator("[name=name]").fill("Розничный покупатель")
                page.locator("[name=phone]").fill("+79991234567")
                page.locator('[name=communication][value=telegram]').check()
                expect(page.locator('[data-checkout-field=telegram]')).to_be_visible()
                page.locator('[name=telegram_use_phone]').check()
                expect(page.locator('[data-checkout-field=telegram]')).to_be_hidden()
                page.locator('[name=communication][value=whatsapp]').check()
                expect(page.locator('[name=whatsapp]')).to_be_visible()
                page.locator('[name=whatsapp]').fill("+79997654321")
                page.locator('[name=comment]').fill("Связаться после 18:00")
                page.reload(wait_until="networkidle")
                expect(page.locator('[name=comment]')).to_have_value("Связаться после 18:00")
                expect(page.locator('[name=telegram_use_phone]')).to_be_checked()
                page.locator("h1").click()
                for width in (360,390,430,768,1440):
                    page.set_viewport_size({"width":width,"height":844 if width<700 else 1000})
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),width)
                    page.screenshot(path=str(output/f"{engine}-cart-{width}.png"),full_page=True)
                page.set_viewport_size({"width":390,"height":844})
                def lose_response(route):
                    route.fetch()
                    route.abort()
                page.route("**/retailer/checkout/",lose_response)
                page.locator('.rs-checkout-form [type=submit]').click()
                expect(page.locator(".rs-form-status")).to_contain_text("Связь прервана")
                page.locator(".rs-status-check").click()
                page.wait_for_url("**/retailer/order/**")
                for width in (360,390,430,768,1440):
                    page.set_viewport_size({"width":width,"height":844 if width<700 else 1000})
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),width)
                    page.screenshot(path=str(output/f"{engine}-success-{width}.png"),full_page=True)
                self.assertEqual(errors,[])
                context.close();browser.close()
        self.assertEqual(Sale.objects.filter(storefront_source="resource_retail").count(),2)
        self.assertFalse(CashTransaction.objects.exists())
        for sale in Sale.objects.filter(storefront_source="resource_retail"):
            self.assertEqual(sale.buyer_contact_methods,["telegram","whatsapp"])
            self.assertEqual(sale.buyer_telegram,"+79991234567")
