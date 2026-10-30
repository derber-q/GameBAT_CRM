"""Пустой рейс → дополнительная партия → привязка обычным заказом в Chromium."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from sales.payment_browser_checks import database_call
from . import test_empty_trips as fixtures
from .models import SupplierOrderBatch


class EmptyTripsBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        fixtures.EmptyTripTests.setUp(self)
        price = fixtures.EmptyTripTests.other_price(self)
        self.normal_order = fixtures.EmptyTripTests.order(self, price)
        self.output = Path(settings.BASE_DIR) / 'outputs/empty-trips-20261027'
        self.output.mkdir(parents=True, exist_ok=True)

    def test_create_additional_goods_and_first_priced_order(self):
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('orders:list'))
            page.get_by_role('link', name='Создать пустой рейс', exact=True).click()
            page.locator('[name="name"]').fill('Сначала дополнительные товары')
            page.get_by_role('button', name='Создать рейс', exact=True).click()
            expect(page).to_have_url(re.compile(r'/crm/orders/trips/\d+/$'))
            pk = int(re.search(r'/trips/(\d+)/', page.url).group(1))
            expect(page.get_by_role('heading', level=1)).to_contain_text('Сначала дополнительные товары')
            self.assertIsNone(run(lambda: SupplierOrderBatch.objects.get(pk=pk).price_list_id))
            page.screenshot(path=str(self.output / 'empty-trip.png'), full_page=True)
            page.get_by_role('link', name='Добавить дополнительные товары', exact=True).click()
            page.locator('[name="calculation_price_list"]').select_option(str(self.price.pk))
            page.locator('[data-addition-search]').first.fill('Игра')
            page.locator('.suggestion').filter(has_text='ADD-CD').click()
            page.locator('[name="lines-0-supplier"]').select_option(str(self.supplier.pk))
            page.locator('[name="lines-0-aed"]').fill('110')
            page.locator('[name="lines-0-customer_price"]').fill('2500')
            page.locator('[name="lines-0-stock_qty"]').fill('2')
            expect(page.locator('[data-addition-cost]').first).to_contain_text('2250.00')
            page.get_by_role('button', name='Продолжить', exact=True).click()
            expect(page).to_have_url(re.compile(r'step=2'))
            page.get_by_role('button', name='Продолжить', exact=True).click()
            expect(page).to_have_url(re.compile(r'step=3'))
            page.get_by_role('button', name='Продолжить', exact=True).click()
            expect(page).to_have_url(re.compile(r'step=4'))
            page.screenshot(path=str(self.output / 'additional-review.png'), full_page=True)
            page.get_by_role('button', name='Создать заказы и добавить в рейс', exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse('orders:trip_detail', args=[pk]))
            def snapshot():
                batch = SupplierOrderBatch.objects.get(pk=pk)
                return batch.price_list_id, list(batch.trip_orders.values_list('pk', flat=True)), list(
                    batch.trip_orders.first().items.values())
            price_id, additional_ids, snapshots = run(snapshot)
            self.assertIsNone(price_id)
            self.assertEqual(len(additional_ids), 1)
            page.get_by_role('link', name='Добавить заказы', exact=True).click()
            page.locator(f'[name="orders"][value="{self.normal_order.pk}"]').check()
            page.get_by_role('button', name='Добавить в рейс', exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse('orders:trip_detail', args=[pk]))
            self.assertEqual(run(lambda: SupplierOrderBatch.objects.get(pk=pk).price_list_id), self.normal_order.price_list_id)
            self.assertEqual(run(lambda: list(SupplierOrderBatch.objects.get(pk=pk).trip_orders.get(
                pk=additional_ids[0]).items.values())), snapshots)
            expect(page.locator('.page-heading')).to_contain_text(f'Прайс №{self.normal_order.price_list_id}')
            page.screenshot(path=str(self.output / 'bound-trip.png'), full_page=True)
            page.goto(self.live_server_url + reverse('orders:list'))
            row = page.locator(f'[data-trip-id="{pk}"]')
            expect(row).to_contain_text('Сначала дополнительные товары')
            expect(row.locator('[data-trip-status]')).to_have_text('В работе')
            page.set_viewport_size({'width': 390, 'height': 900})
            page.get_by_role('link', name='Создать пустой рейс', exact=True).click()
            expect(page.locator('[name="name"]')).to_be_visible()
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            page.screenshot(path=str(self.output / 'create-mobile.png'), full_page=True)
            self.assertEqual(errors, [])
            browser.close()
