"""Сохранение отметки, выделение таблицы и восстановление редактирования в браузере."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import Supplier
from price.services import create_procurement_price_list
from pricing.models import SupplierCDPrice
from .services import create_customer_procurement_order
from .trips import create_trip, change_trip_line


class TripInvoiceBrowserChecks(StaticLiveServerTestCase):
    def test_toggle_persists_and_only_locks_selected_supplier(self):
        actor = User.objects.create_superuser('invoice-browser')
        suppliers = [Supplier.objects.create(name=letter, letter=letter, priority=index,
            legal_entity=letter, phone_1='1', highlight_color='#37A7BA')
            for index, letter in enumerate(('A', 'F'), start=1)]
        product = CD.objects.create(name='PS4 Street Fighter 5', platform=Platform.objects.create(name='PS4'))
        for supplier, price in zip(suppliers, (40, 45)):
            SupplierCDPrice.objects.create(supplier=supplier, cd=product, price=price)
        price = create_procurement_price_list(actor=actor, exchange_rate_usdt_aed=4, exchange_rate_usdt_rub=80,
            delivery_general_usdt_per_kg=0, delivery_devices_usdt_per_kg=0, delivery_storage_usdt_per_kg=0, delivery_cd_rub=0)
        order = create_customer_procurement_order(actor=actor, price_list_id=price.pk, recipient='Заказчик', comment='',
            lines=[{'price_list_item_id': price.items.get(cd=product).pk, 'prepayment_quantity': 0, 'postpayment_quantity': 2}])
        trip = create_trip(actor=actor, order_ids=[order.pk], creation_key=uuid4())
        line = trip.lines.get(cd=product)
        change_trip_line(actor=actor, batch_id=trip.pk, line_id=line.pk, revision=trip.revision,
            quantity=1, action='transfer', target_supplier_id=suppliers[1].pk, price_supplier_id=suppliers[0].pk)
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/trip_invoices_20261023/browser'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('orders:trip_detail', args=[trip.pk]))
            panel = page.locator(f'#trip-supplier-{suppliers[0].pk}')
            other = page.locator(f'#trip-supplier-{suppliers[1].pk}')
            checkbox = panel.get_by_role('checkbox', name='Инвойс принят')
            expect(checkbox).not_to_be_checked()
            expect(panel.locator('.trip-line-form input')).to_have_count(1)
            checkbox.check()
            expect(panel).to_have_class('panel table-panel trip-supplier-panel trip-invoice-accepted')
            expect(checkbox).to_be_checked()
            expect(checkbox).to_be_enabled()
            expect(panel.locator('.trip-line-form')).to_have_count(0)
            expect(panel.locator('[data-trip-price-edit]')).to_have_count(0)
            expect(other.locator('.trip-line-form input')).to_have_count(1)
            expect(panel.get_by_role('link', name='Скачать Excel')).to_be_visible()
            panel.screenshot(path=str(output / 'accepted-wide.png'))
            page.reload()
            expect(checkbox).to_be_checked()
            other_checkbox = other.get_by_role('checkbox', name='Инвойс принят')
            other_checkbox.check()
            expect(other).to_have_class('panel table-panel trip-supplier-panel trip-invoice-accepted')
            expect(checkbox).to_be_enabled()
            expect(other_checkbox).to_be_enabled()
            page.set_viewport_size({'width': 390, 'height': 900})
            panel.screenshot(path=str(output / 'accepted-mobile.png'))
            checkbox.uncheck()
            expect(panel).to_have_class('panel table-panel trip-supplier-panel')
            expect(checkbox).not_to_be_checked()
            expect(panel.locator('.trip-line-form input')).to_have_count(1)
            expect(panel.locator('[data-trip-price-edit]')).to_have_count(1)
            page.reload()
            expect(checkbox).not_to_be_checked()
            # При сетевой ошибке флаг возвращается к последнему сохранённому значению.
            context.route('**/suppliers/*/invoice/', lambda route: route.fulfill(status=503,
                json={'success': False, 'message': 'Тестовая ошибка сохранения'}))
            checkbox.check()
            expect(panel.locator('[data-invoice-error]')).to_have_text('Тестовая ошибка сохранения')
            expect(checkbox).not_to_be_checked()
            expect(checkbox).to_be_enabled()
            self.assertEqual(errors, [])
            browser.close()
