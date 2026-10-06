"""Изолированные браузерные проверки. Запускать явно: manage.py test resource_storefront.browser_checks."""
import json
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright

from catalog.models import CD, Tech, Platform, Brand, ProductType
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock
from .models import StorefrontSettings, WholesaleContact
from .security import issue_link


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class MobileBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        self.output = Path(settings.BASE_DIR) / "outputs" / "resource-mobile" / "after"
        self.output.mkdir(parents=True, exist_ok=True)
        warehouse, _ = Warehouse.objects.get_or_create(name="Проверка мобильной витрины")
        StorefrontSettings.objects.update_or_create(pk=1, defaults={"warehouse": warehouse})
        platform = Platform.objects.create(name="PS5 проверка")
        # Копируются только названия и пути фото для реалистичного тестового наполнения.
        # Все остатки, контакты и продажи создаются исключительно в тестовой БД.
        with sqlite3.connect(f"file:{Path(settings.BASE_DIR) / 'db.sqlite3'}?mode=ro", uri=True) as source:
            samples = source.execute("SELECT name, title_image FROM catalog_cd WHERE is_archived=0 ORDER BY id LIMIT 30").fetchall()
        self.products = []
        for index in range(30):
            name, photo = samples[index % len(samples)] if samples else (f"Игра длинного названия — специальное издание {index}", "")
            product = CD.objects.create(name=name, title_image=photo if index % 3 else "", platform=platform, wholesale_price=1000 + index, cost=500)
            CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=50)
            self.products.append(product)
        brand = Brand.objects.create(name="Sony проверка")
        product_type = ProductType.objects.create(name="Геймпад")
        tech = Tech.objects.create(name="Контроллер беспроводной — длинное название варианта", brand=brand, product_type=product_type, wholesale_price=6500)
        TechWarehouseStock.objects.create(warehouse=warehouse, tech=tech, quantity=50)
        self.contact = WholesaleContact.objects.create(name="Проверка мобильного заказа", phone="+79990000000", address="Тестовый адрес")
        _, self.token = issue_link(self.contact, None)

    def test_mobile_journey(self):
        from playwright.sync_api import expect
        from sales.models import Sale
        from cash.models import CashTransaction
        results = []
        with sync_playwright() as pw:
            for engine in ("chromium", "webkit"):
                browser = getattr(pw, engine).launch()
                context = browser.new_context(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + "/opt/" + self.token + "/", wait_until="networkidle")
                def shot(name):
                    page.screenshot(path=str(self.output / f"{engine}-{name}.png"), full_page=not ("filters" in name or "checkout" in name))
                def fits():
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.viewport_size["width"] + 1)
                shot("home-390")
                page.locator(".rs-search-open").click()
                expect(page.locator("#rs-search")).to_be_focused()
                page.locator(".rs-nav-close").click()
                expect(page.locator(".rs-search-open")).to_be_focused()
                page.locator(".rs-hero-actions a").first.click()
                page.wait_for_load_state("networkidle")
                shot("catalog-390")
                page.locator(".rs-filter-open").click()
                page.locator("#id_category").select_option("cd")
                page.locator("#id_price_min").fill("1001")
                shot("filters-390")
                page.set_viewport_size({"width":390,"height":430})
                page.locator(".rs-filter-actions button").scroll_into_view_if_needed()
                expect(page.locator(".rs-filter-actions button")).to_be_in_viewport()
                page.set_viewport_size({"width":390,"height":844})
                old_url = page.url
                page.locator(".rs-filter-close").click()
                self.assertEqual(page.url, old_url)
                expect(page.locator("#id_price_min")).to_have_value("")
                page.locator(".rs-filter-open").click()
                page.locator("#id_category").select_option("cd")
                page.locator("#id_price_min").fill("1001")
                page.locator(".rs-filter-actions button").click()
                page.wait_for_url("**price_min=1001**")
                page.wait_for_load_state("networkidle")
                expect(page.locator(".rs-filter-chips")).to_contain_text("1001")
                shot("filtered-390")
                page.locator(".rs-card-name").first.click()
                page.wait_for_load_state("networkidle")
                shot("product-390")
                page.locator("[data-catalog-back]").click()
                page.wait_for_load_state("networkidle")
                self.assertIn("price_min=1001", page.url)
                page.goto(self.live_server_url + "/opt/catalog/", wait_until="networkidle")
                if engine == "chromium":
                    cdp = context.new_cdp_session(page)
                    cdp.send("Network.enable")
                    cdp.send("Network.emulateNetworkConditions", {"offline":False,"latency":150,"downloadThroughput":100000,"uploadThroughput":50000})
                    page.reload(wait_until="networkidle")
                    self.assertTrue(page.evaluate("document.fonts.check('16px Manrope')"))
                    shot("catalog-slow-network-390")
                    cdp.send("Network.emulateNetworkConditions", {"offline":False,"latency":0,"downloadThroughput":-1,"uploadThroughput":-1})
                # Сеть оборвана до запроса: сообщение и безопасный повтор того же добавления.
                context.set_offline(True)
                page.locator(".rs-card-buy button[type=submit]").first.click()
                expect(page.locator(".rs-toast")).to_contain_text("Связь прервана")
                context.set_offline(False)
                page.locator(".rs-card-buy button[type=submit]").first.click()
                expect(page.locator(".rs-toast")).to_contain_text("Добавлено")
                page.goto(self.live_server_url + "/opt/cart/", wait_until="networkidle")
                expect(page.locator(".rs-cart-row")).to_have_count(1)
                shot("cart-1-390")
                # 30 отдельных добавлений через HTTP браузера с настоящим CSRF.
                csrf = page.locator('[name="csrfmiddlewaretoken"]').first.input_value()
                for index, product in enumerate(self.products):
                    response = context.request.post(self.live_server_url + "/opt/cart/add/", form={"csrfmiddlewaretoken":csrf,"kind":"cd","product_id":product.pk,"quantity":1,"operation":f"{engine}-{index}"}, headers={"X-Requested-With":"XMLHttpRequest"})
                    self.assertEqual(response.status, 200)
                    if index == 9:
                        page.reload(wait_until="networkidle")
                        expect(page.locator(".rs-cart-row")).to_have_count(10)
                        shot("cart-10-390")
                page.reload(wait_until="networkidle")
                expect(page.locator(".rs-cart-row")).to_have_count(30)
                for width in (360,375,390,412,430,768,1440):
                    page.set_viewport_size({"width":width,"height":844 if width < 768 else 1000})
                    fits()
                    shot(f"cart-30-{width}")
                page.set_viewport_size({"width":844,"height":390})
                fits(); shot("cart-landscape")
                page.set_viewport_size({"width":390,"height":844})
                page.locator(".rs-cart-row").nth(15).scroll_into_view_if_needed()
                y = page.evaluate("window.scrollY")
                row = page.locator(".rs-cart-row").nth(15)
                row.locator('[name="quantity"]').fill("3")
                row.get_by_role("button", name="Изменить").click()
                expect(page.locator(".rs-toast")).to_contain_text("Корзина обновлена")
                self.assertLess(abs(page.evaluate("window.scrollY") - y), 120)
                page.locator(".rs-cart-summary").click()
                page.locator('[name="extra_phone"]').fill("ошибка")
                page.locator('[name="comment"]').fill("Сохранённый комментарий")
                page.reload(wait_until="networkidle")
                expect(page.locator('[name="comment"]')).to_have_value("Сохранённый комментарий")
                page.locator('.rs-checkout-form [type="submit"]').click()
                expect(page.locator('[data-error-for="extra_phone"]')).to_contain_text("Укажите телефон")
                expect(page.locator('[name="comment"]')).to_have_value("Сохранённый комментарий")
                page.locator('[name="extra_phone"]').fill("+7 999 000 00 00")
                shot("checkout-390")
                # Сервер принимает заказ, но ответ теряется: проверяем статус без нового POST.
                def lose_response(route):
                    route.fetch()
                    route.abort()
                page.route("**/opt/checkout/", lose_response)
                page.locator('.rs-checkout-form [type="submit"]').click()
                expect(page.locator(".rs-form-status")).to_contain_text("Связь прервана")
                expect(page.locator('.rs-checkout-form [type="submit"]')).to_be_disabled()
                page.locator(".rs-status-check").click()
                page.wait_for_url("**/opt/order/**")
                shot("success-390")
                page.unroute("**/opt/checkout/", lose_response)
                for width in (360,375,390,412,430,768,1440):
                    page.set_viewport_size({"width":width,"height":844 if width < 768 else 1000})
                    for name, url in (("home","/opt/"),("catalog","/opt/catalog/"),("product",f"/opt/product/cd/{self.products[0].pk}/")):
                        page.goto(self.live_server_url + url, wait_until="networkidle")
                        fits(); shot(f"{name}-{width}")
                        if width == 1440:
                            expect(page.locator(".rs-search-open")).to_be_hidden()
                            expect(page.locator(".rs-mobile-cart")).to_be_hidden()
                            expect(page.locator(".rs-nav-close")).to_be_hidden()
                    if width < 768:
                        targets = page.locator(".rs-buy-detail button").evaluate_all("els=>els.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))")
                        self.assertTrue(all(x["w"] >= 44 and x["h"] >= 44 for x in targets))
                page.set_viewport_size({"width":844,"height":390})
                for name, url in (("home","/opt/"),("catalog","/opt/catalog/"),("product",f"/opt/product/cd/{self.products[0].pk}/")):
                    page.goto(self.live_server_url + url,wait_until="networkidle")
                    fits(); shot(name+"-landscape")
                page.goto(self.live_server_url + "/opt/catalog/?q=несуществующий-товар",wait_until="networkidle")
                expect(page.locator(".rs-empty")).to_contain_text("Товары не найдены")
                page.goto(self.live_server_url + "/opt/catalog/?price_min=2000&price_max=1000",wait_until="networkidle")
                expect(page.locator(".rs-alert")).to_contain_text("не меньше")
                self.assertEqual(errors, [])
                results.append({"engine":engine,"widths":[360,375,390,412,430,768,1440],"cart_sizes":[1,10,30],"lost_checkout_response":"recovered", "js_errors":errors})
                context.close(); browser.close()
        self.assertEqual(Sale.objects.filter(wholesale_contact=self.contact).count(), 2)
        self.assertFalse(CashTransaction.objects.filter(sale__wholesale_contact=self.contact).exists())
        (self.output / "results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
