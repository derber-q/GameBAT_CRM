"""Общая кнопка звука: включение каналов, отказ autoplay и компактная шапка."""
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from sales.notification_browser_checks import FAKE_AUDIO


class SoundButtonBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('sound-icon-browser'))
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 900})
        self.context.add_init_script(FAKE_AUDIO)
        self.context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
            'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
        self.context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.live_server_url + reverse('orders:list'))
        self.button = self.page.locator('[data-notification-sound-enable]')
        expect(self.button).to_be_enabled()

    def tearDown(self):
        self.browser.close()
        self.pw.stop()
        self.assertEqual(self.errors, [])

    def test_one_icon_enables_both_channels_without_test_buttons_or_page_panels(self):
        page = self.page
        expect(self.button).to_have_count(1)
        expect(page.locator('[data-market-sound-enable], [data-avito-sound-enable]')).to_have_count(0)
        expect(self.button).to_have_attribute('aria-label', 'Включить звуковые уведомления')
        for panel in page.locator('.notification-state').all():
            self.assertEqual(panel.bounding_box()['height'], 0)
        self.button.click()
        expect(self.button).to_have_attribute('aria-pressed', 'true')
        expect(self.button).to_be_disabled()
        self.assertEqual(sorted(page.evaluate('window.__audioEvents.map(event => event.channel)')), ['avito', 'market'])
        self.assertEqual(page.evaluate('localStorage.getItem("resource.avito.sound.v1")'), 'true')
        self.assertTrue(page.evaluate('window.GameBAT.marketAlertState ? new window.GameBAT.marketAlertState.IndexedState().enabled() : false'))
        # Включённая кнопка больше не запускает проверочный сигнал.
        self.button.evaluate('node => node.click()')
        self.assertEqual(page.evaluate('window.__audioEvents.length'), 2)
        output = Path(settings.BASE_DIR) / 'outputs/sound-icon-20261027'
        output.mkdir(parents=True, exist_ok=True)
        for width in (1440, 390, 320):
            page.set_viewport_size({'width': width, 'height': 900})
            expect(self.button).to_be_visible()
            expect(self.button).to_have_css('width', '32px')
            box = self.button.bounding_box()
            self.assertGreaterEqual(box['x'], 0)
            self.assertLessEqual(box['x'] + box['width'], width)
            if width <= 390:
                page.locator('.mobile-nav-toggle').click()
                expect(page.locator('.navigation-drawer')).to_be_visible()
                # Иконка остаётся в шапке, а не переносится в скрытый блок настроек.
                self.assertTrue(self.button.evaluate('node => node.parentElement.classList.contains("session-tools")'))
                page.keyboard.press('Escape')
            page.screenshot(path=str(output / f'header-{width}.png'))
        page.reload()
        expect(self.button).to_have_attribute('aria-pressed', 'true')
        expect(self.button).to_be_disabled()
        self.assertEqual(page.evaluate('window.__audioEvents.length'), 0)
        page.goto(self.live_server_url + reverse('admin:index'))
        expect(self.button).to_have_count(1)
        expect(self.button).to_be_visible()
        expect(self.button).to_have_attribute('aria-pressed', 'true')

    def test_blocked_autoplay_can_be_enabled_again_from_the_same_icon(self):
        self.page.evaluate('window.__audioDenied = true')
        self.button.click()
        expect(self.button).to_have_attribute('data-sound-state', 'blocked')
        expect(self.button).to_be_enabled()
        expect(self.button).to_have_attribute('aria-pressed', 'false')
        expect(self.button).to_have_attribute('title', re.compile('Браузер заблокировал звук'))
        self.assertEqual(self.page.evaluate('window.__audioEvents.length'), 0)
        self.page.evaluate('window.__audioDenied = false')
        self.button.click()
        expect(self.button).to_have_attribute('aria-pressed', 'true')
        expect(self.button).to_be_disabled()
        self.assertEqual(self.page.evaluate('window.__audioEvents.length'), 2)

    def test_new_market_order_still_plays_automatically_after_enabling(self):
        from django.utils import timezone
        snapshot = {'count': 0, 'orders': [], 'server_now': timezone.now().isoformat(),
            'repeat_seconds': 600, 'can_acknowledge': False}
        self.context.route('**/crm/sales/market-notifications/', lambda route: route.fulfill(json=snapshot))
        self.page.evaluate('window.GameBAT.refreshMarketNotifications()')
        self.button.click()
        expect(self.button).to_have_attribute('aria-pressed', 'true')
        snapshot['orders'] = [{'id': 123, 'order_id': 321, 'started_at': timezone.now().isoformat()}]
        snapshot['count'] = 1
        self.page.evaluate('window.GameBAT.refreshMarketNotifications()')
        self.page.wait_for_function('window.__audioEvents.some(event => event.channel === "market" && event.id === "123")')
        expect(self.page.locator('[data-market-pending-count]')).to_have_text('1')
        expect(self.button).to_have_attribute('aria-pressed', 'true')
