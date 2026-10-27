"""Поле Telegram и открытие новой вкладки проверяются без обращения к чужому чату."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from sales.payment_browser_checks import database_call
from .models import Partner


class TelegramBrowserChecks(StaticLiveServerTestCase):
    def test_edit_and_open_chat_from_partner_list(self):
        actor = User.objects.create_superuser('telegram-browser')
        partner = Partner.objects.create(name='Игромир')
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/partner_telegram_20261023/browser'
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            context.route('https://web.telegram.org/**', lambda route: route.fulfill(body='Telegram Web: тестовая вкладка'))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('partners:partner_edit', args=[partner.pk]))
            page.locator('#id_telegram').fill('https://t.me/Partner_Contact')
            page.get_by_role('button', name='Сохранить', exact=True).click()
            page.wait_for_url(self.live_server_url + reverse('partners:partner_detail', args=[partner.pk]))
            expect(page.get_by_role('link', name='Открыть чат с Игромир в Telegram')).to_be_visible()
            page.screenshot(path=str(output / 'detail.png'), full_page=True)
            page.goto(self.live_server_url + reverse('partners:partner_list'))
            button = page.get_by_role('link', name='Открыть чат с Игромир в Telegram')
            expect(button).to_have_attribute('href', 'https://web.telegram.org/k/#@Partner_Contact')
            page.screenshot(path=str(output / 'list.png'), full_page=True)
            with page.expect_popup() as popup:
                button.click()
            popup.value.wait_for_load_state()
            self.assertEqual(popup.value.url, 'https://web.telegram.org/k/#@Partner_Contact')
            self.assertEqual(database.submit(database_call,
                lambda: Partner.objects.get(pk=partner.pk).telegram).result(), '@Partner_Contact')
            self.assertEqual(errors, [])
            browser.close()
