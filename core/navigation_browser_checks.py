"""Проверка фактического переполнения шапки и мобильного меню в Chromium."""
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User


class NavigationBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('navigation-browser'))
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.context = self.browser.new_context(viewport={'width': 2200, 'height': 960})
        self.context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
            'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
        self.context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={
            'available': True, 'rates': {'USDT/RUB': {'value': '84.50'}, 'USDT/AED': {'value': '3.67'}}}))
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.live_server_url + reverse('orders:list'))
        expect(self.page.locator('[data-nav-item]')).to_have_count(10)
        self.output = Path(settings.BASE_DIR) / 'outputs/adaptive-navigation-20261027'
        self.output.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.browser.close()
        self.pw.stop()
        self.assertEqual(self.errors, [])

    def settle_layout(self):
        self.page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')

    def test_only_items_that_do_not_fit_move_to_more_and_return_in_order(self):
        page = self.page
        all_labels = page.locator('.main-nav > [data-nav-item]').evaluate_all(
            'items => items.map(item => (item.matches("a") ? item : item.querySelector("a")).textContent.trim())')
        expect(page.locator('[data-nav-overflow]')).to_be_hidden()
        widths = page.locator('.main-nav > [data-nav-item]').evaluate_all('items => items.map(item => item.getBoundingClientRect().width)')
        counts = []
        for width in (1865, 1440, 1100, 900, 761, 1440, 2200):
            page.set_viewport_size({'width': width, 'height': 960})
            self.settle_layout()
            visible = page.locator('.main-nav > [data-nav-item]')
            hidden = page.locator('.nav-overflow-list > [data-nav-item]')
            count = visible.count()
            counts.append(count)
            labels = lambda locator: locator.evaluate_all(
                'items => items.map(item => (item.matches("a") ? item : item.querySelector("a")).textContent.trim())')
            self.assertEqual(labels(visible), all_labels[:count])
            self.assertEqual(labels(hidden), all_labels[count:])
            self.assertEqual(page.locator('[data-nav-item]').count(), len(all_labels))
            nav_box = page.locator('.main-nav').bounding_box()
            more_width = page.locator('.nav-more-button').bounding_box()['width'] if hidden.count() else 0
            self.assertLessEqual(sum(widths[:count]) + more_width, nav_box['width'] + .1)
            if hidden.count():
                self.assertGreater(sum(widths[:count + 1]) + more_width, nav_box['width'])
                page.get_by_role('button', name='Ещё', exact=False).click()
                expect(hidden.first).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.locator('.nav-more-button')).to_be_focused()
                expect(hidden.first).to_be_hidden()
            expect(page.locator('.crm-topbar')).to_have_css('height', '58px')
            header_box = page.locator('.crm-topbar').bounding_box()
            self.assertLessEqual(header_box['x'] + header_box['width'], width)
            if width in (1440, 900):
                page.screenshot(path=str(self.output / f'desktop-{width}.png'))
        self.assertEqual(counts[-1], 10)
        self.assertLess(counts[4], counts[1])
        # На узком экране открываем подраздел скрытого пункта и действительно переходим по ссылке.
        page.set_viewport_size({'width': 900, 'height': 960})
        self.settle_layout()
        page.locator('.nav-more-button').click()
        warehouse = page.locator('.nav-overflow-list [data-warehouse-nav]')
        warehouse.get_by_role('button', name='Подразделы: Склад', exact=True).click()
        warehouse.get_by_role('link', name='Приход', exact=True).click()
        expect(page).to_have_url(self.live_server_url + reverse('supplies:list'))
        # Обновление курсов не должно сбрасывать фокус и закрывать обычное выпадающее меню.
        page.set_viewport_size({'width': 1440, 'height': 960})
        self.settle_layout()
        trigger = page.locator('[data-counterparties-nav] .nav-dropdown-trigger')
        trigger.focus()
        page.locator('[data-rate-symbol="USDT/RUB"] b').evaluate('node => { node.textContent = "1000.00"; }')
        self.settle_layout()
        expect(trigger).to_be_focused()
        expect(page.locator('[data-counterparties-nav]').get_by_role('link', name='Кредиторы', exact=True)).to_be_visible()

    def test_mobile_drawer_rates_profile_keyboard_and_resize(self):
        page = self.page
        for width in (320, 390, 760):
            page.set_viewport_size({'width': width, 'height': 800})
            self.settle_layout()
            expect(page.locator('.crm-topbar')).to_have_css('height', '56px')
            expect(page.locator('.mobile-section-label')).to_have_text('Импорт')
            expect(page.locator('.main-nav')).to_be_hidden()
            expect(page.locator('.drawer-navigation > [data-nav-item]')).to_have_count(10)
            expect(page.locator('.navigation-drawer')).not_to_be_visible()
            self.assertLessEqual(page.locator('.mobile-nav-toggle').bounding_box()['x'] + 40, width)
            page.screenshot(path=str(self.output / f'mobile-{width}-closed.png'))
            page.get_by_role('button', name='Открыть навигацию', exact=True).click()
            expect(page.get_by_role('dialog', name='Навигация', exact=True)).to_be_visible()
            expect(page.locator('[data-rate-symbol="USDT/RUB"] b')).to_have_text('84.50')
            expect(page.locator('[data-rate-symbol="USDT/AED"] b')).to_have_text('3.67')
            expect(page.locator('.drawer-utilities .clock')).to_be_visible()
            expect(page.get_by_role('link', name='Админ-панель', exact=True)).to_be_visible()
            expect(page.get_by_role('button', name='Выйти', exact=True)).to_be_visible()
            expect(page.locator('#gb-date')).to_have_count(1)
            expect(page.locator('[data-market-counter]')).to_have_count(1)
            expect(page.locator('[data-avito-counter]')).to_have_count(1)
            page.screenshot(path=str(self.output / f'mobile-{width}-open.png'))
            page.keyboard.press('Escape')
            expect(page.locator('.navigation-drawer')).not_to_be_visible()
            expect(page.locator('.mobile-nav-toggle')).to_be_focused()
            self.assertFalse(page.locator('html').evaluate('node => node.classList.contains("navigation-drawer-open")'))
        page.set_viewport_size({'width': 390, 'height': 800})
        self.settle_layout()
        page.locator('.mobile-nav-toggle').click()
        page.get_by_role('button', name='Подразделы: Контрагенты', exact=True).click()
        page.get_by_role('link', name='Кредиторы', exact=True).click()
        expect(page).to_have_url(self.live_server_url + reverse('creditors:list'))
        expect(page.locator('.mobile-section-label')).to_have_text('Контрагенты')
        page.locator('.mobile-nav-toggle').click()
        page.mouse.click(5, 400)
        expect(page.locator('.navigation-drawer')).not_to_be_visible()
        page.locator('.mobile-nav-toggle').click()
        page.set_viewport_size({'width': 1865, 'height': 960})
        self.settle_layout()
        expect(page.locator('.navigation-drawer')).not_to_be_visible()
        expect(page.locator('.session-tools > .header-utilities')).to_be_visible()
        expect(page.locator('.header-profile-menu')).to_be_hidden()
        page.locator('.profile-toggle').click()
        expect(page.get_by_role('link', name='Сменить пароль', exact=True)).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.locator('.profile-toggle')).to_be_focused()
        expect(page.locator('.header-profile-menu')).to_be_hidden()

    def test_shared_header_overrides_page_specific_wrapping_and_preserves_brand(self):
        page = self.page
        for endpoint in ('sales:create', 'orders:list', 'pricing:avito_check'):
            page.goto(self.live_server_url + reverse(endpoint))
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 900})
                self.settle_layout()
                expect(page.locator('.crm-topbar')).to_have_css('flex-wrap', 'nowrap')
                expect(page.locator('.crm-topbar')).to_have_css('height', '56px' if width == 390 else '58px')
                logo = page.locator('.brand-logo')
                expect(logo).to_be_visible()
                self.assertTrue(logo.evaluate('image => image.complete && image.naturalWidth > 0'))
                self.assertEqual(page.locator('.brand').inner_text().strip(), '')
                expect(page.locator('.brand')).to_have_attribute('href', reverse('core:home'))
                if width == 1440:
                    rates = page.locator('.header-status .rates').bounding_box()
                    clock = page.locator('.header-status .clock').bounding_box()
                    self.assertGreaterEqual(clock['x'], rates['x'] + rates['width'])
                    admin = page.get_by_role('link', name='Админ-панель', exact=True)
                    expect(admin).to_have_css('width', '32px')
                    admin.hover()
                    expect(admin).to_have_css('background-color', 'rgba(255, 255, 255, 0.12)')
        page.set_viewport_size({'width': 1440, 'height': 900})
        self.settle_layout()
        page.get_by_role('link', name='Админ-панель', exact=True).focus()
        page.keyboard.press('Enter')
        expect(page).to_have_url(self.live_server_url + reverse('admin:index'))

    def test_touch_navigation_on_mobile_chromium_and_webkit(self):
        webkit = self.pw.webkit.launch()
        try:
            for browser in (self.browser, webkit):
                with self.subTest(browser=browser.browser_type.name):
                    phone = browser.new_context(viewport={'width': 390, 'height': 844},
                        is_mobile=True, has_touch=True, device_scale_factor=2)
                    phone.add_cookies(self.context.cookies())
                    phone.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
                    page = phone.new_page()
                    page.on('pageerror', lambda error: self.errors.append(str(error)))
                    # Обычная таблица пока шире телефона; шапка должна вписаться независимо от неё.
                    page.goto(self.live_server_url + reverse('partners:list'))
                    toggle = page.get_by_role('button', name='Открыть навигацию', exact=True)
                    expect(toggle).to_be_visible()
                    self.assertLessEqual(page.locator('.crm-topbar').bounding_box()['width'], 390)
                    toggle.tap()
                    expect(page.get_by_role('dialog', name='Навигация', exact=True)).to_be_visible()
                    page.screenshot(path=str(self.output / f'touch-{browser.browser_type.name}.png'))
                    box = page.locator('.navigation-drawer').bounding_box()
                    self.assertGreaterEqual(box['x'], 0)
                    self.assertLessEqual(box['x'] + box['width'], 390)
                    page.get_by_role('button', name='Подразделы: Склад', exact=True).tap()
                    page.get_by_role('link', name='Приход', exact=True).tap()
                    expect(page).to_have_url(self.live_server_url + reverse('supplies:list'))
                    toggle.tap()
                    page.get_by_role('button', name='Закрыть навигацию', exact=True).tap()
                    expect(page.locator('.navigation-drawer')).not_to_be_visible()
                    phone.close()
        finally:
            webkit.close()
