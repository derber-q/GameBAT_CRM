"""Остатки и места хранения в редакторе до и после приёмки, на тестовой БД."""
from contextlib import closing
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from warehouse.models import WarehouseStorageLocation, CDWarehouseStorageAssignment
from . import test_price_review as review_tests
from .services import accept_supply


class PendingSupplyBrowserChecks(StaticLiveServerTestCase):
    @patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    def test_pending_and_accepted_edit_show_current_inventory_on_two_widths(self):
        review_tests.SupplyPriceReviewTests.setUp(self)
        self.client.force_login(self.user)
        location = WarehouseStorageLocation.objects.create(warehouse=self.warehouse, room="A", rack=1, shelf=2, columns=[])
        CDWarehouseStorageAssignment.objects.create(stock=self.stock, location=location, position=0)
        output = Path(settings.BASE_DIR) / "outputs" / "pending-supply-browser"
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw, closing(connections["default"]):
            browser = pw.chromium.launch()
            for width in (1280, 390):
                supply = review_tests.SupplyPriceReviewTests._pending_supply(self)
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                    "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}])
                context.route("**/crm/api/exchange-rates/", lambda route: route.fulfill(json={"rates": {}, "available": False}))
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse("supplies:edit", args=(supply.pk,)))
                reference = page.locator('[data-supply-stock-reference]')
                expect(reference).to_contain_text("На складе: 2 шт.")
                expect(reference).to_contain_text(location.canonical_value)
                page.locator('[name="quantity"]').fill("3")
                page.screenshot(path=str(output / f"pending-edit-{width}.png"), full_page=True)
                page.get_by_role("button", name="Сохранить без приёмки", exact=True).click()
                expect(page).to_have_url(self.live_server_url + reverse("supplies:detail", args=(supply.pk,)))
                supply.refresh_from_db()
                self.stock.refresh_from_db()
                self.assertEqual((supply.status, supply.total_units, self.stock.quantity), ("price_review", 3, 2))
                accepted = accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=[{
                    "product_type": "cd", "product_id": self.product.pk, "supplier_id": self.supplier.pk,
                    "quantity": 1, "purchase_unit_cost": "200"}])
                page.goto(self.live_server_url + reverse("supplies:edit", args=(accepted.pk,)))
                expect(page.locator('[data-supply-stock-reference]')).to_contain_text("На складе: 3 шт.")
                expect(page.locator('[data-supply-stock-reference]')).to_contain_text(location.canonical_value)
                page.screenshot(path=str(output / f"accepted-edit-{width}.png"), full_page=True)
                self.assertEqual(errors, [])
                context.close()
                if width == 1280:
                    # Следующая ширина снова начинает с того же физического остатка.
                    from .services import cancel_supply
                    cancel_supply(actor=self.user, supply_id=accepted.pk, comment="Очистка тестового сценария")
            browser.close()
