"""Уменьшение строк рейса в Chromium на отдельной тестовой БД."""
import os
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import Supplier
from price.services import create_procurement_price_list
from pricing.models import SupplierCDPrice
from .services import create_customer_procurement_order
from .trips import change_trip_line, create_trip, _assert_balances


class TripReductionsBrowserChecks(StaticLiveServerTestCase):
    @patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    def test_last_supplier_automatic_manual_and_non_last_choice_on_two_widths(self):
        user = User.objects.create_superuser("reduction-browser", password="IsolatedTest123!")
        self.client.force_login(user)
        suppliers = [Supplier.objects.create(name=name, letter=letter, priority=priority,
            highlight_color="#37A7BA", legal_entity=letter, phone_1="1")
            for name, letter, priority in (("Я — первый", "A", 1), ("Второй", "F", 2), ("А — последний", "M", 3))]
        cd = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра уменьшения", sku="RED-001")
        for supplier, amount in zip(suppliers, (100, 110, 120)):
            SupplierCDPrice.objects.create(supplier=supplier, cd=cd, price=amount)
        price = create_procurement_price_list(actor=user, exchange_rate_usdt_aed=4, exchange_rate_usdt_rub=80,
            delivery_general_usdt_per_kg=0, delivery_devices_usdt_per_kg=0,
            delivery_storage_usdt_per_kg=0, delivery_cd_rub=0)
        source = price.items.get()

        def make_trip(amounts, last=True):
            orders = [create_customer_procurement_order(actor=user, price_list_id=price.pk,
                recipient=f"Заказчик {index}", comment="", lines=[{"price_list_item_id": source.pk,
                "prepayment_quantity": 0, "postpayment_quantity": amount}]) for index, amount in enumerate(amounts)]
            trip = create_trip(actor=user, order_ids=[order.pk for order in orders], creation_key=uuid4())
            line = trip.lines.get()
            if last:
                change_trip_line(actor=user, batch_id=trip.pk, line_id=line.pk, revision=trip.revision,
                    quantity=0, action="transfer", target_supplier_id=suppliers[2].pk, price_supplier_id=suppliers[0].pk)
                line = trip.lines.get(supplier=suppliers[2])
            return trip, line, orders

        output = Path(settings.BASE_DIR) / "outputs" / "trip-reductions-browser"
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

                def visit(trip):
                    page.goto(self.live_server_url + reverse("orders:trip_detail", args=(trip.pk,)))

                def edit(line, quantity):
                    row = page.locator(f'[data-trip-line="{line.pk}"]')
                    row.locator('[name="quantity"]').fill(str(quantity))
                    row.get_by_role("button", name="Изменить", exact=True).click()

                # Один заказ: уменьшение сохраняется сразу, без открытия диалога.
                trip, line, orders = make_trip((10,))
                visit(trip)
                with page.expect_navigation(wait_until="domcontentloaded"):
                    edit(line, 6)
                self.assertEqual(orders[0].items.get().quantity, 6)
                expect(page.locator('#trip-change-dialog')).not_to_be_visible()
                page.screenshot(path=str(output / f"single-order-{width}.png"), full_page=True)

                # Несколько заказов: перенос скрыт, сумма ручного распределения обязательна.
                trip, line, orders = make_trip((5, 5))
                visit(trip)
                edit(line, 7)
                expect(page.locator('#trip-change-mode')).not_to_be_visible()
                expect(page.locator('#trip-transfer-fields')).not_to_be_visible()
                expect(page.locator('#trip-allocation-fields')).to_be_visible()
                page.locator('#trip-change-save').click()
                expect(page.locator('#trip-change-error')).to_contain_text("Распределите количество")
                page.get_by_role("spinbutton", name="Получит Заказчик 0", exact=True).fill("5")
                page.get_by_role("spinbutton", name="Получит Заказчик 1", exact=True).fill("2")
                page.screenshot(path=str(output / f"manual-orders-{width}.png"))
                page.locator('#trip-change-save').click()
                expect(page.locator('#trip-change-dialog')).not_to_be_visible()
                self.assertEqual([order.items.get().quantity for order in orders], [5, 2])

                # Ноль у трёх заказов: сразу сохраняется, строки и история остаются.
                trip, line, orders = make_trip((5, 3, 2))
                visit(trip)
                with page.expect_navigation(wait_until="domcontentloaded"):
                    edit(line, 0)
                expect(page.locator(f'[data-trip-line="{line.pk}"]')).to_have_class("trip-zero-row")
                self.assertEqual([order.items.get().quantity for order in orders], [0, 0, 0])
                page.screenshot(path=str(output / f"zero-orders-{width}.png"), full_page=True)
                _assert_balances(trip)

                # Восстановление нуля по-прежнему требует ручного распределения.
                edit(line, 2)
                expect(page.locator('#trip-allocation-fields')).to_be_visible()
                page.locator('#trip-change-cancel').click()
                self.assertEqual(trip.lines.get(pk=line.pk).quantity, 0)

                # Первый поставщик: сохраняется выбор, отказ от переноса не требует таблицы.
                trip, line, orders = make_trip((5, 3, 2), last=False)
                visit(trip)
                edit(line, 0)
                expect(page.locator('#trip-change-mode')).to_be_visible()
                expect(page.locator('#trip-transfer-fields')).to_be_visible()
                page.locator('#trip-action').select_option("adjust")
                expect(page.locator('#trip-allocation-fields')).not_to_be_visible()
                expect(page.locator('#trip-automatic-adjustment')).to_be_visible()
                page.screenshot(path=str(output / f"non-last-zero-{width}.png"))
                page.locator('#trip-change-save').click()
                expect(page.locator('#trip-change-dialog')).not_to_be_visible()
                self.assertEqual([order.items.get().quantity for order in orders], [0, 0, 0])
                self.assertEqual(trip.lines.count(), 1)

                # Совпадение максимальных приоритетов оставляет явный выбор и пояснение.
                suppliers[1].priority = 3
                suppliers[1].save(update_fields=("priority",))
                trip, line, orders = make_trip((10,))
                visit(trip)
                edit(line, 6)
                expect(page.locator('#trip-change-mode')).to_be_visible()
                expect(page.locator('#trip-priority-ambiguity')).to_be_visible()
                page.locator('#trip-action').select_option("adjust")
                expect(page.locator('#trip-allocation-fields')).not_to_be_visible()
                page.screenshot(path=str(output / f"equal-priorities-{width}.png"))
                page.locator('#trip-change-save').click()
                expect(page.locator('#trip-change-dialog')).not_to_be_visible()
                self.assertEqual(orders[0].items.get().quantity, 6)
                suppliers[1].priority = 2
                suppliers[1].save(update_fields=("priority",))
                self.assertEqual(errors, [])
                context.close()
            browser.close()
