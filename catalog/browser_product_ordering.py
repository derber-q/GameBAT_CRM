"""Браузерная проверка вложенных таблиц в отдельной тестовой базе."""
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from accounts.models import User
from .test_product_ordering import create_ordering_fixture, ordering_pages


class ProductOrderingBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        User.objects.create_superuser("ordering-browser", password="test-password")
        self.warehouse, self.products, self.cds = create_ordering_fixture()

    def test_nested_collapse_search_and_price_save(self):
        output = Path("outputs/product-ordering")
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            context.route("**/api/exchange-rates/", lambda route: route.fulfill(
                status=200, content_type="application/json", body='{"available": false, "rates": {}}',
            ))
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse("accounts:login"))
            page.locator('[name="username"]').fill("ordering-browser")
            page.locator('[name="password"]').fill("test-password")
            page.locator('button[type="submit"]').click()
            page.wait_for_function("!location.pathname.endsWith('/login/')")
            for url in ordering_pages(self.warehouse):
                with self.subTest(url=url):
                    page.goto(self.live_server_url + url)
                    brands = page.locator('[data-collapse-toggle][aria-controls*="-brand-"]')
                    self.assertEqual(brands.count(), 5)
                    self.assertEqual(brands.first.locator('.section-name').inner_text(), "Sony")
                    brand_id = brands.first.get_attribute("aria-controls")
                    body = page.locator(f'#{brand_id}')
                    child = body.locator('[data-collapse-toggle]').first
                    type_id = child.get_attribute("aria-controls")
                    table = page.locator(f'#{type_id}')
                    child.click()
                    self.assertFalse(table.is_visible())
                    brands.first.click()
                    self.assertFalse(body.is_visible())
                    self.assertTrue(brands.nth(1).is_visible())
                    brands.first.click()
                    self.assertTrue(body.is_visible())
                    self.assertFalse(table.is_visible())
                    child.click()
                    self.assertTrue(table.is_visible())
                    # Оставляем первые два типа открытыми, остальные сворачиваем для снимка.
                    for toggle in body.locator('[data-collapse-toggle]').all()[2:]:
                        toggle.click()
                    for toggle in brands.all()[1:]:
                        toggle.click()
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(output / f'{brand_id.split("-brand-")[0]}-desktop.png'), full_page=True)
                    page.locator('[name="search"]').fill("Nintendo item 0")
                    page.locator('[data-product-filters]').locator('button[type="submit"]').click()
                    page.wait_for_url("**/*search=*")
                    self.assertEqual(page.locator('[aria-controls*="-brand-"]').count(), 1)
                    self.assertEqual(page.locator('[aria-controls*="-brand-"] .section-name').inner_text(), "Nintendo")
            page.goto(self.live_server_url + reverse("pricing:list"))
            product = self.products[0]
            form_id = f"product-price-tech-{product.pk}"
            form = page.locator(f'#{form_id}')
            page.locator(f'[form="{form_id}"][name="wholesale_price"]').fill("333.50")
            original_url = page.url
            with page.expect_response(lambda response: response.request.method == "POST") as pending:
                form.locator('button[type="submit"]').click()
            self.assertEqual(pending.value.status, 200)
            page.wait_for_function("Array.from(document.querySelectorAll('[role=status]')).some(el => el.textContent === 'Сохранено')")
            self.assertEqual(page.url, original_url)
            self.assertFalse(errors, errors)
            context.close()
            browser.close()
        product.refresh_from_db()
        self.assertEqual(product.wholesale_price, Decimal("333.50"))
