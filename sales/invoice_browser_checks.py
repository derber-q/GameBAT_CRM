"""Скачивание накладной из карточки продажи на отдельной тестовой БД."""
from io import BytesIO
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from openpyxl import load_workbook
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .services import create_sale


class InvoiceBrowserChecks(StaticLiveServerTestCase):
    @patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    def test_existing_button_downloads_true_excel_without_sale_changes(self):
        user = User.objects.create_superuser("invoice-browser", password="StrongAdmin!123")
        self.client.force_login(user)
        warehouse = Warehouse.objects.create(name="Склад накладной")
        product = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра для накладной",
                                    sku="000001", cost=100, avito_price=250)
        CDWarehouseStock.objects.create(cd=product, warehouse=warehouse, quantity=5)
        sale = create_sale(actor=user, warehouse_id=warehouse.pk, price_type="retail", sale_type="retail",
            payment_method="cash_postpay", lines=[{"product_type": "cd", "product_id": product.pk, "quantity": 2}])
        unchanged = (sale.updated_at, sale.order_status, sale.payment_status, sale.total_amount)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (1280, 390):
                context = browser.new_context(viewport={"width": width, "height": 900}, accept_downloads=True)
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}])
                context.route("**/crm/api/exchange-rates/", lambda route: route.fulfill(json={"rates": {}, "available": False}))
                page = context.new_page()
                page.goto(self.live_server_url + reverse("sales:detail", args=(sale.pk,)))
                button = page.get_by_role("link", name="Скачать накладную Excel", exact=True)
                expect(button).to_have_count(1)
                with page.expect_download() as download:
                    button.click()
                self.assertEqual(download.value.suggested_filename, f"nakladnaya_{sale.visible_id}.xlsx")
                book = load_workbook(BytesIO(Path(download.value.path()).read_bytes()))
                self.assertEqual(book.active["C5"].value, product.name)
                self.assertEqual(book.active["D5"].value, "000001")
                self.assertEqual(book.active["G6"].value, 500)
                book.close()
                context.close()
            browser.close()
        sale.refresh_from_db()
        self.assertEqual((sale.updated_at, sale.order_status, sale.payment_status, sale.total_amount), unchanged)
