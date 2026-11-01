"""Реальный Chromium и отдельная БД; ОС, внешние API и принтер не запускаются."""
from datetime import timedelta
from pathlib import Path
import uuid

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from integrations.models import IntegrationCredential
from integrations.worker_models import WorkerController, WorkerService


class WorkerBrowserChecks(StaticLiveServerTestCase):
    def test_autoplay_blocked_and_new_incident_uses_same_global_button(self):
        user = User.objects.create_user('worker-autoplay')
        self.client.force_login(user)
        now = timezone.now()
        WorkerController.objects.create(mode='managed', heartbeat_at=now)
        IntegrationCredential.objects.create(provider='avito', encrypted_client_id='test',
            encrypted_client_secret='test', last_success_at=now)
        WorkerService.objects.create(code='avito', expected='required', status='stopped',
            observed_at=now, incident=uuid.uuid4(), incident_started_at=now)
        snapshot = self.client.get(reverse('integrations:worker_status')).json()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'available': False, 'rates': {}}))
            context.route('**/crm/integrations/workers/status/', lambda route: route.fulfill(json=snapshot))
            context.add_init_script('''
                window.__allow = false; window.__plays = 0;
                window.Audio = class {
                    constructor() {this.dataset = {};}
                    play() {window.__plays++; if (!window.__allow) return Promise.reject(new DOMException('Blocked', 'NotAllowedError'));
                        setTimeout(() => this.onended?.(), 10); return Promise.resolve();}
                    pause() {}
                };
            ''')
            page = context.new_page()
            page.goto(self.live_server_url + reverse('integrations:workers'))
            button = page.locator('[data-notification-sound-enable]')
            button.click()
            expect(button).to_have_attribute('data-sound-state', 'blocked')
            expect(page.locator('[data-worker-alert]')).to_be_visible()
            page.evaluate('window.__allow = true')
            button.click()
            expect(button).to_have_attribute('data-sound-state', 'on')
            page.wait_for_timeout(100)
            before = page.evaluate('window.__plays')
            snapshot['incidents'] = [{'id': str(uuid.uuid4()), 'started_at': now.isoformat()}]
            page.get_by_role('button', name='Обновить', exact=True).click()
            page.wait_for_function('(n) => window.__plays === n + 1', arg=before)
            browser.close()

    def test_staff_layout_sound_cycles_tabs_recovery_and_network_failure(self):
        user = User.objects.create_user('worker-browser')
        self.client.force_login(user)
        now = timezone.now()
        IntegrationCredential.objects.create(provider='avito', encrypted_client_id='test',
            encrypted_client_secret='test', last_success_at=now)
        WorkerController.objects.create(mode='managed', heartbeat_at=now)
        incident = uuid.uuid4()
        WorkerService.objects.create(code='avito', expected='required', status='stopped',
            observed_at=now, incident=incident, incident_started_at=now)
        output = Path(settings.BASE_DIR) / 'outputs/worker_monitoring/browser'
        output.mkdir(parents=True, exist_ok=True)
        snapshot = self.client.get(reverse('integrations:worker_status')).json()
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1366, 'height': 1000})
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'available': False, 'rates': {}}))
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.add_init_script('''
                window.__plays = 0;
                window.Audio = class {
                    constructor() {this.dataset = {};}
                    play() {window.__plays++; setTimeout(() => this.onended?.(), 10); return Promise.resolve();}
                    pause() {}
                };
            ''')
            pages = [context.new_page(), context.new_page()]
            errors = []
            for page in pages:
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse('integrations:workers'))
                expect(page.locator('[data-worker-row]')).to_have_count(4)
                expect(page.locator('[data-worker-alert]')).to_be_visible()
                expect(page.locator('[data-worker-row="avito"] [data-field="status_label"]')).to_have_text('Остановлен')
                expect(page.get_by_role('button', name='Восстановить все')).to_have_count(0)
                expect(page.get_by_role('link', name='API ключи', exact=True)).to_have_count(0)
            page = pages[0]
            page.get_by_role('button', name='Включить звуковые уведомления').click()
            expect(page.locator('[data-notification-sound-enable]')).to_have_attribute('data-sound-state', 'on')
            page.screenshot(path=str(output / 'desktop.png'))
            page.reload()
            expect(page.locator('[data-notification-sound-enable]')).to_have_attribute('data-sound-state', 'on')
            page.wait_for_timeout(200)
            self.assertEqual(page.evaluate('window.__plays'), 0, 'Перезагрузка не повторяет текущий звуковой цикл')

            # Переносим фактическое время инцидента и server_time на следующий цикл,
            # одновременно опрашиваем в двух настоящих вкладках с общим IndexedDB.
            snapshot['server_time'] = (now + timedelta(minutes=10, seconds=1)).isoformat()
            for tab in pages:
                tab.route('**/crm/integrations/workers/status/', lambda route: route.fulfill(json=snapshot))
            pages[1].reload()
            for tab in pages:
                tab.get_by_role('button', name='Обновить', exact=True).click()
            pages[0].wait_for_timeout(300)
            self.assertEqual(sum(tab.evaluate('window.__plays') for tab in pages), 1)

            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.locator('[data-worker-alert]')).to_be_visible()
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            page.screenshot(path=str(output / 'mobile.png'))
            page.get_by_role('button', name='Открыть навигацию').click()
            page.keyboard.press('Escape')

            snapshot['alarm'] = False
            snapshot['incidents'] = []
            snapshot['services'][0].update(status='running', status_label='Работает', alarm=False)
            page.get_by_role('button', name='Обновить', exact=True).click()
            expect(page.locator('[data-worker-alert]')).to_be_hidden()
            page.unroute('**/crm/integrations/workers/status/')
            page.route('**/crm/integrations/workers/status/', lambda route: route.abort())
            page.get_by_role('button', name='Обновить', exact=True).click()
            expect(page.locator('[data-worker-alert]')).to_be_visible()
            expect(page.locator('[data-worker-summary]')).to_contain_text('Нет актуальных данных')
            self.assertEqual(errors, [])
            browser.close()
