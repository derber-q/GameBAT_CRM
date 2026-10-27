"""Проверки создания площадок в Chromium на отдельной тестовой базе."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from sales.payment_browser_checks import database_call
from .models import Partner, SalesPlatform


class PlatformBrowserChecks(StaticLiveServerTestCase):
    def test_standalone_and_inline_creation(self):
        actor = User.objects.create_superuser('platform-browser')
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/platform_create_20261023/browser'
        output.mkdir(parents=True, exist_ok=True)
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
            page.goto(self.live_server_url + reverse('consignment:list'))
            page.get_by_role('link', name='Создать площадку', exact=True).click()
            page.locator('#id_name').fill('Магазин на Арбате')
            page.locator('#id_address').fill('Москва, Арбат, 1')
            page.locator('#id_legal_entity').fill('ООО Магазин')
            page.locator('#id_phone_1').fill('+7 999 123-45-67')
            page.screenshot(path=str(output / 'standalone.png'), full_page=True)
            page.get_by_role('button', name='Создать площадку', exact=True).click()
            platform = run(lambda: SalesPlatform.objects.get(name='Магазин на Арбате'))
            page.wait_for_url(self.live_server_url + reverse('consignment:platform', args=[platform.pk]))

            page.goto(self.live_server_url + reverse('partners:partner_create'))
            fields = page.locator('[data-new-platform]')
            expect(fields).to_be_hidden()
            page.locator('#id_name').fill('Партнёр Игромир')
            page.locator('#id_address').fill('Москва, Садовая, 2')
            page.locator('#id_phone_1').fill('00123456789')
            page.locator('#id_create_platform').check()
            expect(fields).to_be_visible()
            expect(page.locator('#id_platform')).to_be_disabled()
            expect(page.locator('#id_new_platform-name')).to_have_value('Партнёр Игромир')
            expect(page.locator('#id_new_platform-address')).to_have_value('Москва, Садовая, 2')
            expect(page.locator('#id_new_platform-phone_1')).to_have_value('00123456789')
            page.locator('#id_new_platform-name').fill('Площадка Игромир')
            page.locator('#id_new_platform-legal_entity').fill('ИП Иванов')
            page.locator('#id_create_platform').uncheck()
            expect(fields).to_be_hidden()
            expect(page.locator('#id_platform')).to_be_enabled()
            page.locator('#id_create_platform').check()
            expect(page.locator('#id_new_platform-name')).to_have_value('Площадка Игромир')
            page.screenshot(path=str(output / 'inline.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 900})
            page.screenshot(path=str(output / 'mobile.png'), full_page=True)
            page.get_by_role('button', name='Сохранить', exact=True).click()
            page.wait_for_url(re.compile(r'/partners/\d+/$'))
            partner = run(lambda: Partner.objects.select_related('platform', 'creditor').get(name='Партнёр Игромир'))
            self.assertEqual(partner.platform.name, 'Площадка Игромир')
            self.assertEqual(partner.platform.phone_1, '00123456789')
            self.assertEqual(partner.creditor.current_debt, 0)
            self.assertEqual(errors, [])
            browser.close()
