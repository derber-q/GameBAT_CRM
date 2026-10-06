"""Браузерная проверка ревизии в отдельной тестовой БД."""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from catalog.models import CD, Tech, Platform, Brand, ProductType
from .models import Warehouse, CDWarehouseStock, TechWarehouseStock, WarehouseRevision
from .storage_services import update_storage_locations


class RevisionBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="revision-browser", password="test-password")
        self.warehouse = Warehouse.objects.create(name="Основной склад")
        platform = Platform.objects.create(name="Nintendo Switch 2")
        self.game = CD.objects.create(name="NS2 Animal Crossing: New Horizons — Nintendo Switch 2 Edition", platform=platform)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.game, quantity=12)
        second = CD.objects.create(name="NS2 Civilization VII", platform=platform)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=second, quantity=3)
        tech = Tech.objects.create(name="Контроллер Nintendo Switch 2 Pro Controller", brand=Brand.objects.create(name="Nintendo"), product_type=ProductType.objects.create(name="Геймпады"))
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech, quantity=2)
        update_storage_locations(actor=self.user, warehouse_id=self.warehouse.pk, product_type="cd", product_id=self.game.pk, raw_value=r"A1-2-1\2, A6-3, B12-6-1")

    def test_mobile_devices_shared_marks_confirmation_and_failures(self):
        output = Path("outputs/warehouse-revision")
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            for engine in ("chromium", "webkit"):
                browser = getattr(playwright, engine).launch(headless=True)
                context = browser.new_context(viewport={"width": 390, "height": 844})
                context.route('**/api/exchange-rates/', lambda route: route.fulfill(status=200, content_type='application/json', body='{"available": false, "rates": {}}'))
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                def login(target):
                    target.goto(self.live_server_url + reverse("accounts:login"))
                    target.locator('[name="username"]').fill("revision-browser")
                    target.locator('[name="password"]').fill("test-password")
                    target.locator('button[type="submit"]').click()
                    target.wait_for_function("!location.pathname.endsWith('/login/')")
                login(page)
                page.goto(self.live_server_url + reverse("warehouse:revision", args=[self.warehouse.pk]))
                if engine == "chromium":
                    initial = page.locator(f'[data-kind="cd"][data-product-id="{self.game.pk}"]')
                    self.assertTrue(initial.locator('input').is_enabled())
                    initial.locator('label').click()
                    page.wait_for_function("document.querySelector('[data-progress-count]').textContent === '1 / 3'")
                    self.assertTrue(initial.locator('input').is_checked())
                    self.assertNotEqual(page.locator('[data-revision-list]').get_attribute('data-revision-id'), '')
                    page.reload()
                    self.assertTrue(initial.locator('input').is_checked())
                page.get_by_role('button', name='Новая ревизия', exact=True).click()
                self.assertTrue(page.locator('dialog').is_visible())
                page.get_by_role('button', name='Отмена', exact=True).click()
                self.assertFalse(page.locator('dialog').is_visible())
                page.get_by_role('button', name='Новая ревизия', exact=True).click()
                page.get_by_role('button', name='Начать ревизию', exact=True).click()
                page.wait_for_function("document.querySelector('[data-revision-list]').dataset.revisionId !== ''")
                card = page.locator(f'[data-revision-card][data-kind="cd"][data-product-id="{self.game.pk}"]')
                card.locator('label').click()
                page.wait_for_function("document.querySelector('[data-progress-count]').textContent === '1 / 3'")
                self.assertTrue(card.locator('input').is_checked())
                for width in (320, 360, 390, 430, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.evaluate('window.scrollTo(0, 0)')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    self.assertGreaterEqual(card.locator('label').bounding_box()['height'], 44)
                    page.screenshot(path=str(output / f'{engine}-{width}.png'), full_page=True)
                other_context = browser.new_context(viewport={"width": 360, "height": 800})
                other_context.route('**/api/exchange-rates/', lambda route: route.fulfill(status=200, content_type='application/json', body='{"available": false, "rates": {}}'))
                second = other_context.new_page()
                login(second)
                second.goto(self.live_server_url + reverse("warehouse:revision", args=[self.warehouse.pk]))
                self.assertEqual(second.locator('[data-progress-count]').inner_text(), '1 / 3')
                page.get_by_role('link', name='По местам хранения', exact=True).click()
                self.assertTrue(card.locator('input').is_checked())
                self.assertEqual(page.locator(f'[data-kind="cd"][data-product-id="{self.game.pk}"]').count(), 1)
                page.route('**/revision/check/', lambda route: route.abort())
                card.locator('label').click()
                page.wait_for_function("document.querySelector('.revision-card.has-error') !== null")
                self.assertTrue(card.locator('input').is_checked())
                page.unroute('**/revision/check/')
                card.locator('label').click()
                page.wait_for_function("document.querySelector('[data-progress-count]').textContent === '0 / 3'")
                self.assertFalse(card.locator('input').is_checked())
                page.get_by_role('button', name='Новая ревизия', exact=True).click()
                page.get_by_role('button', name='Начать ревизию', exact=True).click()
                page.wait_for_url('**/revision/')
                stale = second.locator(f'[data-kind="cd"][data-product-id="{self.game.pk}"]')
                stale.locator('label').click()
                second.wait_for_function("document.querySelector('.revision-card.has-error') !== null")
                self.assertIn('закрыта', stale.locator('[data-revision-feedback]').inner_text())
                self.assertFalse(errors, errors)
                other_context.close()
                context.close()
                browser.close()
        self.assertEqual(WarehouseRevision.objects.filter(warehouse=self.warehouse, is_active=True).count(), 1)
