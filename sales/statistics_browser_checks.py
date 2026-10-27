"""Читаемость карточек, раскрытие операций и состав продаж в Chromium."""
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from creditors.services import adjust_creditor_debt
from partners.models import Partner
from warehouse.models import CDWarehouseStock, Warehouse
from .services import create_sale, mark_sale_paid, advance_order_status


class StatisticsBrowserChecks(StaticLiveServerTestCase):
    def test_cards_are_readable_and_operations_start_collapsed(self):
        actor = User.objects.create_superuser('stats-layout-browser')
        warehouse = Warehouse.objects.create(name='Варфоломеева 265')
        partner = Partner.objects.create(name='Игромир — магазин видеоигр и техники')
        product = CD.objects.create(name='PS5 Игра с длинным названием — полное коллекционное издание',
            platform=Platform.objects.create(name='PS5'), wholesale_price='26990.99', avito_price='29990', cost='20000')
        CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        for index, method in enumerate(('cash', 'bank_transfer_postpay', 'partner_debt')):
            sale = create_sale(actor=actor, warehouse_id=warehouse.pk, price_type='wholesale', sale_type='wholesale',
                partner_id=partner.pk, payment_method=method, note='Максим и Рома\nСамовывоз в пятницу' if not index else '',
                lines=[{'product_type': 'cd', 'product_id': product.pk, 'quantity': index + 1}])
            if method == 'bank_transfer_postpay':
                mark_sale_paid(actor=actor, sale_id=sale.pk)
                for status in ('assembled', 'delivered'):
                    advance_order_status(actor=actor, sale_id=sale.pk, next_status=status)
        # Достаточно операций, чтобы проверить независимую пагинацию сворачиваемого журнала.
        for index in range(50):
            adjust_creditor_debt(actor=actor, creditor_id=partner.creditor_id, warehouse_id=warehouse.pk,
                money_source_type='offset', new_debt=100000 + index, comment='Проверка страниц журнала')
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/statistics_layout_20261023/browser'
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
            url = self.live_server_url + reverse('statistics:index')
            page.goto(url)
            toggle = page.locator('[aria-controls="stats-all-operations-content"]')
            content = page.locator('#stats-all-operations-content')
            expect(toggle).to_have_attribute('aria-expanded', 'false')
            expect(content).to_be_hidden()
            toggle.click()
            expect(content).to_be_visible()
            content.get_by_role('link', name='Следующая →').click()
            expect(page.locator('#stats-all-operations .stats-pages')).to_contain_text('2 / 2')
            expect(toggle).to_have_attribute('aria-expanded', 'true')
            content.get_by_role('link', name='← Предыдущая').click()
            expect(page.locator('#stats-all-operations .stats-pages')).to_contain_text('1 / 2')
            expect(content).to_be_visible()
            toggle.click()
            expect(content).to_be_hidden()
            for width in (1440, 1024, 390):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.goto(url)
                card = page.locator('.stats-sale-card').first
                expect(card).to_be_visible()
                payment = card.locator('.stats-sale-meta').filter(has=page.get_by_text('Оплата', exact=True))
                self.assertGreaterEqual(payment.bounding_box()['width'], 100)
                self.assertLess(payment.locator('strong').bounding_box()['height'], 85)
                for current in page.locator('.stats-sale-card').all():
                    self.assertTrue(current.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'))
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'))
                page.locator('.stats-sales-section').screenshot(path=str(output / f'sales-{width}.png'))
                card.get_by_role('button', name='Состав', exact=True).click()
                expect(card.locator('.stats-sale-detail')).to_be_visible()
                card.screenshot(path=str(output / f'expanded-{width}.png'))
                card.get_by_role('button', name='Свернуть', exact=True).click()
                expect(card.locator('.stats-sale-detail')).to_be_hidden()
            self.assertEqual(errors, [])
            browser.close()
