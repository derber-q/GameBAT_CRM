"""Проверка реальных форм и JS в Chromium на отдельной тестовой БД."""
from contextlib import closing
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from partners.models import Supplier
from price.models import ProcurementPriceList, ProcurementPriceListItem

from .models import Brand, CD, Platform, ProductType, Tech
from .newness import newness_expiry


class CatalogFeaturesBrowserChecks(StaticLiveServerTestCase):
    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_create_edit_options_and_rounded_pricing_on_desktop_and_phone(self):
        self.user = User.objects.create_superuser('feature-browser')
        self.platform = Platform.objects.create(name='Nintendo Switch 2')
        self.brand = Brand.objects.create(name='Sony')
        self.product_type = ProductType.objects.create(name='Игровая консоль')
        self.supplier = Supplier.objects.create(name='M', letter='M', highlight_color='#37A7BA', legal_entity='M', phone_1='1')
        cd = CD.objects.create(platform=self.platform, name='Проверка округления', sku='BROWSER-PRICE')
        price = ProcurementPriceList.objects.create(created_by=self.user, exchange_rate_aed_rub=1)
        item = ProcurementPriceListItem.objects.create(price_list=price, product_kind='cd', cd=cd,
            product_name_snapshot=cd.name, article_snapshot=cd.sku, selected_supplier=self.supplier,
            supplier_price_aed=2800, exchange_rate_aed_rub=1, base_price_rub=2800, delivery_rub=0,
            original_markup_rub=201, markup_rub=210, prepayment_price_rub=3010, postpayment_price_rub=3130,
            prepayment_rounding_extra_rub=9, postpayment_rounding_extra_rub=3, postpayment_surcharge_rub=126)
        self.client.force_login(self.user)
        output = Path(settings.BASE_DIR) / 'outputs' / 'catalog_features_20261020' / 'browser'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw, closing(connections['default']):
            browser = pw.chromium.launch()
            for width in (1280, 390):
                context = browser.new_context(viewport={'width': width, 'height': 900})
                context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                for kind, model in (('cd', CD), ('tech', Tech)):
                    page.goto(self.live_server_url + reverse('nomenclature:create') + '?kind=' + kind)
                    expect(page.locator('[name="newness_months"]')).to_have_value('1')
                    expect(page.locator('[name="newness_custom_months"]')).to_be_hidden()
                    page.locator('[name="newness_months"]').select_option('custom')
                    expect(page.locator('[name="newness_custom_months"]')).to_be_visible()
                    page.locator('[name="newness_custom_months"]').fill('7')
                    name = f'Новая карточка {kind} {width}'
                    page.locator('[name="name"]').fill(name)
                    if kind == 'cd':
                        page.locator('[name="platform"]').select_option(str(self.platform.pk))
                    else:
                        page.locator('[name="brand"]').select_option(str(self.brand.pk))
                        page.locator('[name="product_type"]').select_option(str(self.product_type.pk))
                    checkbox = page.locator(f'[name="excluded_suppliers"][value="{self.supplier.pk}"]')
                    checkbox.check()
                    page.locator('[data-newness-options]').screenshot(path=str(output / f'options-{kind}-{width}.png'))
                    page.screenshot(path=str(output / f'create-{kind}-{width}.png'), full_page=True)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    page.get_by_role('button', name='Создать наименование', exact=True).click()
                    expect(page.get_by_role('heading', name=name, exact=True)).to_be_visible()
                    product = model.objects.get(name=name)
                    self.assertEqual(product.creation_source, model.CreationSource.WEB)
                    self.assertEqual(product.newness_until, newness_expiry(product.created_at, 7))
                    expect(page.locator('[name="newness_months"]')).to_have_value('custom')
                    checkbox = page.locator(f'[name="excluded_suppliers"][value="{self.supplier.pk}"]')
                    expect(checkbox).to_be_checked()
                    checkbox.uncheck()
                    page.get_by_role('button', name='Сохранить изменения', exact=True).click()
                    expect(checkbox).not_to_be_checked()
                    product.refresh_from_db()
                    self.assertFalse(product.supplier_exclusions.exists())
                    self.assertEqual(product.newness_until, newness_expiry(product.created_at, 7))
                    page.screenshot(path=str(output / f'edit-{kind}-{width}.png'), full_page=True)
                page.goto(self.live_server_url + reverse('price:procurement_detail', args=(price.pk,)))
                page.locator('[data-markup]').fill('201.01')
                expect(page.locator('[data-prepayment]')).to_have_value('3010.00')
                expect(page.locator('[data-postpayment]')).to_have_value('3130.00')
                expect(page.locator('[data-effective-markup]')).to_have_text('210.00')
                expect(page.locator('[data-prepayment-rounding]')).to_have_count(0)
                expect(page.locator('[data-postpayment-rounding]')).to_have_count(0)
                page.screenshot(path=str(output / f'pricing-{width}.png'), full_page=True)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                for _repeat in range(2):
                    page.get_by_role('button', name='Сохранить расчёт', exact=True).click()
                    expect(page.locator('[data-markup]')).to_have_value('201.01')
                    item.refresh_from_db()
                    self.assertEqual(str(item.prepayment_price_rub), '3010.00')
                    self.assertEqual(str(item.postpayment_price_rub), '3130.00')
                    self.assertEqual(str(item.prepayment_rounding_extra_rub), '8.99')
                self.assertEqual(errors, [])
                context.close()
            browser.close()
