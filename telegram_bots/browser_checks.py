"""Настоящий Chromium, изолированная БД, полный запрет внешних запросов."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from playwright.sync_api import sync_playwright, expect
from accounts.models import User
from .models import StaffBot, StaffBotAccess, StaffBotJob, StaffBotJobDocument, StaffBotUpdate


class TelegramBrowserChecks(StaticLiveServerTestCase):
    def test_admin_employee_link_and_test_stub(self):
        folder = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(TELEGRAM_STAFF_TOKEN_FILE=Path(folder)/'token'))
        self.enterContext(patch.dict('os.environ', {'GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN': ''}))
        admin = User.objects.create_superuser('bot-ui-admin')
        employee = User.objects.create_user('bot-ui-employee')
        employee.user_permissions.add(Permission.objects.get(codename='generate_wholesale_price'))
        bot = StaffBot.objects.create(username='StaffTestBot', enabled=True)
        from partners.models import Supplier
        supplier = Supplier.objects.create(name='Поставщик журнала', letter='A')
        access = StaffBotAccess.objects.create(bot=bot, user=admin, allowed=True, telegram_user_id=500)
        receipt = StaffBotUpdate.objects.create(bot=bot, update_id=500)
        job = StaffBotJob.objects.create(bot=bot, access=access, update=receipt, chat_id=500,
            function='supplier_price_templates', supplier=supplier, state='partial')
        StaffBotJobDocument.objects.create(job=job, product_kind='cd', state='done', telegram_message_id=101)
        StaffBotJobDocument.objects.create(job=job, product_kind='tech', state='error', error_category='forbidden')
        self.client.force_login(admin)
        employee_client = Client()
        employee_client.force_login(employee)
        employee_cookie = employee_client.cookies[settings.SESSION_COOKIE_NAME].value
        output = Path(settings.BASE_DIR) / 'outputs/telegram_staff_20261102'
        output.mkdir(exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1100})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(self.live_server_url + '/') else route.abort())
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + '/crm/integrations/telegram/')
            expect(page.get_by_role('heading', name='Бот сотрудников', exact=True)).to_be_visible()
            expect(page.locator('[name="token"]')).to_have_attribute('type', 'password')
            expect(page.get_by_role('columnheader', name='Шаблоны с ценами', exact=True)).to_be_visible()
            expect(page.get_by_text('Диски: Отправлен', exact=False)).to_be_visible()
            expect(page.get_by_text('Техника: Ошибка', exact=True)).to_be_visible()
            expect(page.get_by_text('Частично отправлен', exact=True)).to_be_visible()
            row = page.locator('tr').filter(has_text=employee.username)
            row.get_by_role('button', name='Разрешить бота', exact=True).click()
            expect(row.get_by_role('button', name='Ссылка подключения', exact=True)).to_be_visible()
            row.get_by_role('button', name='Ссылка подключения', exact=True).click()
            expect(page.get_by_role('link', name='Одноразовая ссылка подключения сотрудника', exact=True)).to_have_attribute('href', __import__('re').compile(r'https://t.me/StaffTestBot\?start=[A-Za-z0-9_-]{43}'))
            page.screenshot(path=str(output / 'admin.png'), full_page=True)
            context.close()
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': employee_cookie, 'url': self.live_server_url}])
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(self.live_server_url + '/') else route.abort())
            page = context.new_page()
            page.goto(self.live_server_url + '/crm/integrations/telegram/connect/')
            page.get_by_role('button', name='Привязать Telegram', exact=True).click()
            expect(page.get_by_role('link', name='Открыть бота и подключиться', exact=True)).to_be_visible()
            expect(page.get_by_role('heading', name='Доступ сотрудников', exact=True)).to_have_count(0)
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            page.screenshot(path=str(output / 'employee-mobile.png'), full_page=True)
            with override_settings(GAMEBAT_ENV='local_test'):
                page.goto(self.live_server_url + '/crm/integrations/telegram/connect/')
                expect(page.get_by_text('Тестовый режим. Взаимодействие с Telegram отключено.', exact=True)).to_be_visible()
                expect(page.get_by_role('button', name='Привязать Telegram', exact=True)).to_have_count(0)
                page.screenshot(path=str(output / 'test-stub.png'), full_page=True)
            self.assertEqual(errors, [])
            browser.close()
