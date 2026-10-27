"""Два счётчика в шапке, переход к действиям и обновление без вызовов Avito."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from catalog.models import Brand, ProductType, Tech
from sales.payment_browser_checks import database_call
from sales.notification_browser_checks import FAKE_AUDIO
from warehouse.models import TechWarehouseStock, CDWarehouseStock
from .models import AvitoListingConnection, AvitoProductProfile, AvitoRemoteListing
from . import test_required_actions


class AvitoCounterBrowserChecks(StaticLiveServerTestCase):
    def test_sound_detects_new_action_at_same_count_once_across_tabs(self):
        self._check_sound_across_tabs()

    def test_sound_without_web_locks_on_local_network(self):
        self._check_sound_across_tabs(without_locks=True)

    def _check_sound_across_tabs(self, *, without_locks=False):
        test_required_actions.RequiredActionsTests.setUp(self)
        self.client.force_login(self.admin)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_init_script(FAKE_AUDIO)
            if without_locks:
                context.add_init_script("Object.defineProperty(navigator, 'locks', {value: undefined})")
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            pages = [context.new_page(), context.new_page()]
            for page in pages:
                page.goto(self.live_server_url + reverse('sales:market_pending'))
                expect(page.locator('[data-avito-action-count]')).to_have_text('1')
            pages[0].locator('[data-avito-sound-enable]').click()
            expect(pages[0].locator('[data-avito-sound-status]')).to_contain_text('Звук Avito включён')
            def total():
                return sum(page.evaluate('window.__audioEvents.length') for page in pages)
            self.assertEqual(total(), 1)
            def switch_action():
                CDWarehouseStock.objects.filter(cd=self.cd).update(quantity=3)
                AvitoRemoteListing.objects.filter(pk=self.listing.pk).update(status='old')
            run(switch_action)
            for page in pages:
                page.evaluate("window.dispatchEvent(new Event('focus'))")
            deadline = time.monotonic() + 8
            while total() < 2 and time.monotonic() < deadline:
                pages[0].wait_for_timeout(50)
            self.assertEqual(total(), 2)
            for page in pages:
                expect(page.locator('[data-avito-action-count]')).to_have_text('1')
                page.evaluate("window.dispatchEvent(new Event('focus'))")
            pages[0].wait_for_timeout(400)
            self.assertEqual(total(), 2)
            pages[1].reload()
            pages[1].wait_for_timeout(400)
            self.assertEqual(pages[1].evaluate('window.__audioEvents.length'), 0)
            browser.close()

    def test_counter_links_refresh_zero_admin_mobile_and_offline(self):
        test_required_actions.RequiredActionsTests.setUp(self)
        self.client.force_login(self.admin)
        tech = Tech.objects.create(name='Техника для публикации', brand=Brand.objects.create(name='Avito test'),
            product_type=ProductType.objects.create(name='Avito test'))
        TechWarehouseStock.objects.create(tech=tech, warehouse=self.warehouse, quantity=3)
        profile = AvitoProductProfile.objects.create(tech=tech, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(avito_item_id=1002, title='Publish test', status='old',
            url='https://www.avito.ru/test_1002')
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        output = Path(settings.BASE_DIR) / 'outputs/avito_counter_20261022'
        output.mkdir(parents=True, exist_ok=True)
        errors = []
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            context.route('https://www.avito.ru/**', lambda route: route.abort())
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('sales:market_pending'))
            counter = page.locator('[data-avito-counter]')
            badge = counter.locator('[data-avito-action-count]')
            expect(badge).to_have_text('2')
            expect(counter).to_have_attribute('title', 'Avito: опубликовать — 1, снять — 1. По последним данным CRM.')
            self.assertTrue(page.locator('[data-market-counter]').evaluate(
                '(node) => node.nextElementSibling.hasAttribute("data-avito-counter")'))
            expect(counter.locator('img')).to_be_visible()
            self.assertTrue(counter.locator('img').evaluate('(node) => node.complete && node.naturalWidth > 0'))
            self.assertEqual(counter.bounding_box()['width'], 40)
            counter.hover()
            expect(counter).to_have_css('background-color', 'rgb(255, 231, 166)')
            page.locator('.session-tools').screenshot(path=str(output / 'header.png'))
            page.goto(self.live_server_url + reverse('orders:stock_create'))
            page.set_viewport_size({'width': 390, 'height': 900})
            counter.scroll_into_view_if_needed()
            box = counter.bounding_box()
            self.assertGreaterEqual(box['x'], 0)
            self.assertLessEqual(box['x'] + box['width'], 390)
            page.locator('.session-tools').screenshot(path=str(output / 'header-mobile.png'))
            page.set_viewport_size({'width': 1440, 'height': 1000})
            counter.click()
            expect(page).to_have_url(self.live_server_url + reverse('integrations:avito') + '#required-actions')
            section = page.locator('#required-actions')
            expect(section.get_by_role('heading')).to_have_text('Необходимые действия: 2')
            link = section.get_by_role('link', name=self.listing.title, exact=True)
            expect(link).to_have_attribute('href', self.listing.url)
            expect(link).to_have_attribute('target', '_blank')
            def resolve_actions():
                CDWarehouseStock.objects.filter(cd=self.cd).update(quantity=3)
                AvitoRemoteListing.objects.filter(pk=listing.pk).update(status='active')
            run(resolve_actions)
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            expect(badge).to_have_text('0')
            expect(section.get_by_role('heading')).to_have_text('Необходимые действия: 0')
            expect(counter).not_to_have_class('market-alert-counter avito-alert-counter has-pending')
            page.goto(self.live_server_url + reverse('admin:index'))
            page.mouse.move(0, 800)
            market_box = page.locator('[data-market-counter]').bounding_box()
            self.assertLessEqual(counter.bounding_box()['x'] - market_box['x'] - market_box['width'], 24)
            expect(badge).to_have_text('0')
            run(lambda: CDWarehouseStock.objects.filter(cd=self.cd).update(quantity=0))
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            expect(badge).to_have_text('1')
            expect(counter).to_have_css('background-color', 'rgb(255, 241, 201)')
            page.locator('#header').screenshot(path=str(output / 'admin.png'))
            context.route('**/avito/actions/count/*', lambda route: route.fulfill(status=503, json={'error': 'offline'}))
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            expect(counter).to_have_attribute('title', 'Avito: показаны последние данные. Не удалось обновить счётчик.')
            expect(badge).to_have_text('1')
            self.assertEqual(errors, [])
            browser.close()
