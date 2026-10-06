"""Изолированная визуальная проверка страницы на desktop и mobile."""
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from .models import AvitoPriceCheckResult, AvitoProductProfile, AvitoRemoteListing, AvitoListingConnection
from .reef_settings import save_key
from .avito_check import CHECK_VERSION, _check_signature


@override_settings(INTEGRATION_ENCRYPTION_KEY=Fernet.generate_key().decode())
class AvitoCheckBrowser(StaticLiveServerTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="check-browser", password="test-password")
        warehouse = Warehouse.objects.create(name="Браузерный склад")
        product = CD.objects.create(name="PlayStation 5 Slim Disc", platform=Platform.objects.create(name="PS5"),
                                    cost=35000, wholesale_price=40000, avito_price=45000)
        CDWarehouseStock.objects.create(cd=product, warehouse=warehouse, quantity=4)
        profile = AvitoProductProfile.objects.create(cd=product)
        AvitoListingConnection.objects.create(profile=profile, remote_listing=AvitoRemoteListing.objects.create(avito_item_id=123456789))
        save_key("browser-test-placeholder")

    def test_mobile_and_desktop_layout(self):
        output = Path("outputs/avito-check")
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            for engine_name in ("chromium", "webkit"):
                browser = getattr(playwright, engine_name).launch(headless=True)
                context = browser.new_context(viewport={"width": 390, "height": 844})
                page = context.new_page()
                page.goto(self.live_server_url + reverse("accounts:login"))
                page.locator('input[name="username"]').fill("check-browser")
                page.locator('input[name="password"]').fill("test-password")
                page.locator('button[type="submit"]').click()
                page.wait_for_function("!location.pathname.endsWith('/login/')")
                page.goto(self.live_server_url + reverse("pricing:avito_check"))
                self.assertTrue(page.get_by_role('link', name='Автоматическая проверка', exact=True).is_visible())
                page.locator('[data-found-price-form] input[name="price"]').fill('39000.50')
                page.locator('[data-found-price-form] button').click()
                page.wait_for_function("document.querySelector('[data-save-status]').textContent === 'Сохранено'")
                self.assertNotEqual(page.locator('[data-found-date]').inner_text(), '—')
                page.reload()
                self.assertEqual(page.locator('[data-found-price-form] input[name="price"]').input_value(), '39000.50')
                self.assertEqual(page.get_by_role('link', name='Ручной поиск').get_attribute('target'), '_blank')
                page.screenshot(path=str(output / f'{engine_name}-list.png'), full_page=True)
                page.get_by_role('link', name='Автоматическая проверка', exact=True).click()
                self.assertIn("Avito Check", page.content(), (engine_name, page.url))
                for width in (390, 1440):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.screenshot(path=str(output / f"{engine_name}-{width}.png"), full_page=True)
                    overflow = page.evaluate("""() => [...document.querySelector('.page').querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > innerWidth).slice(0, 8).map(e => [e.tagName,e.className,Math.round(e.getBoundingClientRect().right)])""")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width, overflow)
                page.locator('.nav-dropdown-trigger').filter(has_text='Ценообразование').hover()
                self.assertTrue(page.get_by_role('link', name='Avito Check').is_visible())
                page.locator('#check-avito').fill('46000')
                modes = []
                def fake_check(product, kind, **kwargs):
                    modes.append(kwargs)
                    offers = [{"ad_id": "123", "title": "PlayStation 5 Slim Disc", "price": "44000",
                               "url": "https://www.avito.ru/moskva/igry_123", "image": "", "seller": "Магазин"}]
                    AvitoPriceCheckResult.objects.update_or_create(profile=product.avito_profile, defaults={
                        "offers": offers, "checked_at": timezone.now(), "metadata": {
                            "version": CHECK_VERSION, "signature": _check_signature(product, kind),
                            "mode": kwargs["mode"], "search_requests": 2, "listing_requests": 3, "cached_listings": 0, "credits": 7,
                        },
                    })
                    return offers
                with patch("pricing.avito_check_views.run_check", side_effect=fake_check):
                    page.locator('#avito-check-run button[value="check"]').click()
                    page.get_by_role('link', name='Открыть на Avito').wait_for()
                    page.wait_for_function("!document.querySelector('#avito-check-run button').disabled")
                    page.locator('#avito-check-run button[value="refresh"]').click()
                    page.wait_for_function("!document.querySelector('#avito-check-run button').disabled")
                    page.locator('#avito-check-run button[value="deep"]').click()
                    page.wait_for_function("!document.querySelector('#avito-check-run button').disabled")
                    self.assertEqual(modes, [{"mode": "economy", "force": False}, {"mode": "economy", "force": True}, {"mode": "deep", "force": False}])
                self.assertEqual(page.locator('#check-avito').input_value(), '46000')
                context.close()
                browser.close()
