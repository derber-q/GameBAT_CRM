"""Реальный Chromium на изолированной SQLite, без Telegram и рабочих операций."""
import os
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect
from accounts.models import User
from catalog.models import SystemProduct
from .models import Buyer, Supplier, DigitalOrder
from .services import move_balance


class DigitalBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        self.enterContext(patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())))
        self.user = User.objects.create_superuser(username='digital-browser')
        self.client.force_login(self.user)
        self.buyer = Buyer.objects.create(name='Browser Buyer')
        self.supplier = Supplier.objects.create(name='Browser Supplier')
        move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='1000', kind='opening', reason='Browser Test')

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_manual_completion_secret_reveal_and_mobile(self):
        output = Path(settings.BASE_DIR) / 'outputs/digital_sales_20261106'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw, closing(connections['default']):
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.route('https://**/*', lambda route: route.abort())
            def fulfill(payload):
                return lambda route: route.fulfill(json=payload)
            for pattern, payload in [('**/crm/api/exchange-rates/**', {'rates': {}, 'available': False}),
                    ('**/crm/sales/market-notifications/**', {'orders': [], 'count': 0}),
                    ('**/crm/integrations/avito/actions/count/**', {'actions': [], 'count': 0})]:
                context.route(pattern, fulfill(payload))
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            page.goto(self.live_server_url + reverse('digital_sales:manual'))
            page.locator('[name="supplier"]').select_option(str(self.supplier.pk))
            page.locator('[name="buyer"]').select_option(str(self.buyer.pk))
            page.locator('[name="items"]').fill('Synthetic Browser Game | 250\nSynthetic Extra | 50')
            page.locator('[name="price"]').fill('500')
            page.locator('[name="secret"]').fill('SYNTHETIC-SECRET-BROWSER')
            page.get_by_role('button', name='Сохранить', exact=True).click()
            page.wait_for_url('**/crm/digital/orders/*/')
            self.assertEqual(DigitalOrder.objects.count(), 1)
            expect(page.get_by_role('button', name='Завершить продажу и списать баланс')).to_be_visible()
            self.assertNotIn('SYNTHETIC-SECRET-BROWSER', page.content())
            page.get_by_role('button', name='Завершить продажу и списать баланс').click()
            expect(page.get_by_text('Продажа завершена', exact=False).first).to_be_visible()
            self.assertEqual(self.buyer.balance, 500)
            page.screenshot(path=str(output / 'order-desktop.png'), full_page=True)
            page.get_by_role('button', name='Показать данные / оригинал').click()
            expect(page.locator('pre')).to_have_text('SYNTHETIC-SECRET-BROWSER')
            page.goto(self.live_server_url + reverse('digital_sales:dashboard'))
            page.screenshot(path=str(output / 'dashboard-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(output / 'dashboard-mobile.png'), full_page=True)
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            self.assertEqual(errors, [])
            browser.close()
