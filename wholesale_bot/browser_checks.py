"""Chromium на отдельной тестовой БД, без Telegram и рабочих интеграций."""
import os
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect
from accounts.models import User
from partners.models import Partner
from .models import Customer


class WholesaleBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='opt-browser')
        self.partner = Partner.objects.create(name='Синтетический оптовый покупатель')
        self.customer = Customer.objects.create(telegram_id=777, status='pending', first_name='Покупатель')
        self.client.force_login(self.user)

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_authorize_revoke_and_mobile(self):
        output = Path(settings.BASE_DIR) / 'outputs/wholesale_bot_20261107'
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
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('price:index'))
            page.get_by_role('link', name='Открыть покупателей и заявки').click()
            page.locator(f'#partner-{self.customer.pk}').select_option(str(self.partner.pk))
            page.get_by_role('button', name='Авторизовать', exact=True).click()
            expect(page.get_by_role('button', name='Отозвать доступ')).to_be_visible()
            self.customer.refresh_from_db()
            self.assertEqual(self.customer.status, 'authorized')
            page.screenshot(path=str(output / 'customers-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            # Общая навигация переносит пункты после resize через requestAnimationFrame.
            page.wait_for_function('document.documentElement.scrollWidth <= window.innerWidth + 1')
            page.screenshot(path=str(output / 'customers-mobile.png'), full_page=True)
            page.get_by_role('button', name='Отозвать доступ').click()
            self.customer.refresh_from_db()
            self.assertEqual(self.customer.status, 'revoked')
            self.assertEqual(errors, [])
            browser.close()
