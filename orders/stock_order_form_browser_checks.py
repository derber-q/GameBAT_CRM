"""Ручной складской заказ на двух ширинах; только тестовая БД и подменённые курсы."""
from contextlib import closing
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from .models import CustomerProcurementOrder
from .test_stock_order_form import create_stock_form_fixture


class StockOrderFormBrowserChecks(StaticLiveServerTestCase):
    @patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    def test_import_page_form_preview_back_and_creation_on_two_widths(self):
        create_stock_form_fixture(self)
        self.client.force_login(self.user)
        output = Path(settings.BASE_DIR) / "outputs/stock-order-form-browser"
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw, closing(connections["default"]):
            browser = pw.chromium.launch()
            for width in (1280, 390):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}])
                context.route("**/crm/api/exchange-rates/", lambda route: route.fulfill(json={"rates": {}, "available": False}))
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("price:imports"))
                page.locator(f'a[href="{reverse("orders:stock_create")}?price_list={self.price.pk}"]').click()
                expect(page.get_by_role("heading", name="Заказ на склад через форму", exact=True)).to_be_visible()
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                cd = page.locator(f'[name="quantity_{self.cd_source.pk}"]')
                tech = page.locator(f'[name="quantity_{self.tech_source.pk}"]')
                cd.fill("3")
                tech.fill("2")
                expect(page.locator("[data-stock-order-total]")).to_have_text("12 470,75")
                expect(page.locator("[data-stock-order-units]")).to_have_text("5")
                search = page.get_by_role("searchbox", name="Поиск товара")
                search.fill("000-CD-FORM")
                expect(cd).to_be_visible()
                expect(tech).to_be_hidden()
                expect(page.locator("[data-stock-order-total]")).to_have_text("12 470,75")
                search.fill("Нет такого товара")
                expect(page.locator("[data-stock-order-no-results]")).to_be_visible()
                search.fill("")
                expect(tech).to_be_visible()
                page.locator('[name="recipient"]').fill(f"Закупка {width}")
                page.locator('[name="comment"]').fill("Через форму")
                expect(page.get_by_role("link", name="Загрузить заказ из Excel", exact=True)).to_be_visible()
                page.screenshot(path=str(output / f"form-{width}.png"), full_page=True)
                page.get_by_role("button", name="Проверить и показать состав", exact=True).click()
                expect(page.get_by_role("columnheader", name="Количество", exact=True)).to_be_visible()
                page.get_by_role("link", name="Изменить состав", exact=True).click()
                expect(cd).to_have_value("3")
                expect(tech).to_have_value("2")
                expect(page.locator('[name="comment"]')).to_have_value("Через форму")
                cd.fill("4")
                page.get_by_role("button", name="Проверить и показать состав", exact=True).click()
                page.screenshot(path=str(output / f"preview-{width}.png"), full_page=True)
                page.get_by_role("button", name="Создать заказ", exact=True).click()
                order = CustomerProcurementOrder.objects.get(recipient=f"Закупка {width}")
                expect(page.get_by_role("heading", name=f"Заказ на склад №{order.pk}", exact=True)).to_be_visible()
                self.assertEqual((order.purpose, order.status, order.total_units), ("stock", "created", 6))
                self.assertEqual(order.items.get(cd=self.cd).prepayment_unit_price, self.cd_source.stock_unit_cost)
                self.assertEqual(errors, [])
                context.close()
            browser.close()
