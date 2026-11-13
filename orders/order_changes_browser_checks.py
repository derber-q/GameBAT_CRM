"""Проверка новых действий заказов и массовой корректировки в настоящем браузере."""
import os
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect

from accounts.models import User
from .models import CustomerProcurementOrder
from .test_arrival_finalization import ArrivalFinalizationFixture


class OrderChangesBrowserChecks(ArrivalFinalizationFixture, StaticLiveServerTestCase):
    def isolate_background(self, context):
        # Фоновый опрос проверяется своим набором; здесь он не должен конкурировать за тестовую SQLite.
        def handler(payload):
            return lambda route:route.fulfill(json=payload)

        for pattern, payload in (
            ('**/crm/api/exchange-rates/**', {'rates':{}, 'available':False}),
            ('**/crm/sales/market-notifications/**', {'orders':[], 'count':0}),
            ('**/crm/integrations/avito/actions/count/**', {'actions':[], 'count':0}),
        ):
            context.route(pattern, handler(payload))

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE':'true'})
    def test_edit_order_and_add_catalog_item_via_autocomplete(self):
        from catalog.models import CD
        from .trips import _assert_balances
        product = CD.objects.create(name='Browser Added Game', sku='BROWSER-ADDED',
            platform=self.cd.platform, weight_grams=100)
        with sync_playwright() as pw, closing(connections['default']):
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width':1440, 'height':1000})
            self.isolate_background(context)
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url':self.live_server_url}])
            page = context.new_page()
            page.goto(self.live_server_url + reverse('orders:edit', args=[self.order.pk]))
            page.locator('[name="postpayment_quantity"]').fill('12')
            page.get_by_role('button', name='Сохранить состав', exact=True).click()
            page.wait_for_url(self.live_server_url + reverse('orders:detail', args=[self.order.pk]))
            self.assertEqual(self.order.items.get().quantity, 12)
            page.goto(self.live_server_url + reverse('orders:add_catalog_items', args=[self.order.pk]))
            page.locator('[name="lines-0-label"]').fill('Browser Added')
            choice = page.get_by_role('button', name='Browser Added Game', exact=False)
            expect(choice).to_be_visible()
            self.assertNotIn('undefined', choice.inner_text())
            choice.click()
            page.locator('[name="lines-0-supplier"]').select_option(str(self.supplier.pk))
            page.locator('[name="lines-0-supplier_price_aed"]').fill('90')
            page.locator('[name="lines-0-customer_price"]').fill('3000')
            page.locator('[name="lines-0-quantity"]').fill('3')
            page.get_by_role('button', name='Добавить в заказ', exact=True).click()
            page.wait_for_url(self.live_server_url + reverse('orders:trip_detail', args=[self.trip.pk]))
            page.wait_for_load_state('networkidle')
            self.assertEqual(self.order.items.get(cd=product).quantity, 3)
            _assert_balances(self.trip)
            browser.close()

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE':'true'})
    def test_bulk_costs_validate_whole_selection_and_apply_once(self):
        self.prepare()
        output = Path(settings.BASE_DIR) / 'outputs/review_20261106'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw, closing(connections['default']):
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width':1440, 'height':1000})
            self.isolate_background(context)
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route:route.fulfill(json={'rates':{}, 'available':False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error:errors.append(str(error)))
            page.goto(self.live_server_url + reverse('orders:arrival_finalization', args=[self.trip.pk]))
            rows = page.locator('.finalization-row')
            expect(rows).to_have_count(2)
            original = rows.first.locator('[name="corrected_cost"]').input_value()
            rows.first.locator('[name="selected_product"]').check()
            page.locator('[data-bulk-cost-operation]').select_option('add')
            page.locator('[data-bulk-cost-amount]').fill('100')
            page.locator('[data-bulk-cost-apply]').click()
            expect(rows.first.locator('[name="corrected_cost"]')).to_have_value('2606.01')
            expect(page.locator('[data-bulk-cost-amount]')).to_have_value('')
            page.locator('[data-bulk-cost-apply]').click()
            expect(rows.first.locator('[name="corrected_cost"]')).to_have_value('2606.01')
            expect(page.locator('[data-finalization-error]')).not_to_be_empty()
            rows.last.locator('[name="selected_product"]').check()
            page.locator('[data-bulk-cost-operation]').select_option('subtract')
            page.locator('[data-bulk-cost-amount]').fill('9999')
            page.locator('[data-bulk-cost-apply]').click()
            expect(rows.first.locator('[name="corrected_cost"]')).to_have_value('2606.01')
            expect(rows.last.locator('[name="corrected_cost"]')).to_have_value(original)
            rows.first.locator('[name="selected_product"]').uncheck()
            page.locator('[data-bulk-cost-amount]').fill('500')
            page.locator('[data-bulk-cost-apply]').click()
            expect(rows.last.locator('[name="corrected_cost"]')).to_have_value('2006.01')
            expect(page.locator('[data-apply-finalization]')).to_be_enabled()
            page.screenshot(path=str(output/'bulk-cost-adjustment.png'), full_page=True)
            page.locator('[data-apply-finalization]').click()
            page.wait_for_url(self.live_server_url + reverse('orders:trip_detail', args=[self.trip.pk]))
            self.arrival.refresh_from_db()
            self.assertTrue(self.arrival.finalized)
            self.assertFalse(errors, errors)
            browser.close()

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE':'true'})
    def test_employee_can_delete_unassigned_order_without_trip_form(self):
        employee = User.objects.create_user('browser-order-editor', password='test')
        employee.user_permissions.add(*Permission.objects.filter(content_type__app_label='orders',
            codename__in=['view_orders', 'edit_created_order']))
        order = self.make_order('customer', 2)
        self.client.force_login(employee)
        with sync_playwright() as pw, closing(connections['default']):
            browser = pw.chromium.launch()
            context = browser.new_context()
            self.isolate_background(context)
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url':self.live_server_url}])
            page = context.new_page()
            page.goto(self.live_server_url + reverse('orders:list'))
            button = page.locator(f'button[form="delete-unassigned-order-{order.pk}"]')
            expect(button).to_be_visible()
            with page.expect_request(lambda req:req.method=='POST' and req.url.endswith(f'/{order.pk}/delete/')):
                page.once('dialog', lambda dialog:dialog.accept())
                button.click()
            page.wait_for_load_state('networkidle')
            expect(page.locator(f'button[form="delete-unassigned-order-{order.pk}"]')).to_have_count(0)
            self.assertFalse(CustomerProcurementOrder.objects.filter(pk=order.pk).exists())
            browser.close()
