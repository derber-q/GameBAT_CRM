"""Проверка плотности финализации рейса в настоящем Chromium."""
import os
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect
from .test_arrival_finalization import ArrivalFinalizationFixture


class ArrivalLayoutBrowserChecks(ArrivalFinalizationFixture, StaticLiveServerTestCase):
    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_compact_table_and_existing_distribution_controls(self):
        self.prepare()
        self.cd.name='NS2 Assassin’s Creed Shadows Special Edition (rus sub)'
        self.cd.save(update_fields=['name'])
        output=Path(settings.BASE_DIR)/'outputs/trip_finalization_layout_20261026'
        output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw, closing(connections['default']):
            browser=pw.chromium.launch()
            context=browser.new_context(viewport={'width':1440,'height':1000})
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page=context.new_page(); errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse('orders:arrival_finalization',args=[self.trip.pk]))
            table=page.locator('.trip-finalization-table'); rows=table.locator('.finalization-row')
            expect(rows).to_have_count(2)
            for width in (1600,1440,1280,1024):
                page.set_viewport_size({'width':width,'height':1000})
                self.assertTrue(table.locator('..').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'),width)
                self.assertTrue(table.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'),width)
                self.assertLessEqual(rows.first.bounding_box()['height'],70,width)
                rows.last.locator('td').last.scroll_into_view_if_needed()
                expect(rows.last.locator('td').last).to_be_in_viewport()
                page.screenshot(path=str(output/f'compact-{width}.png'),full_page=True)
            rows.first.locator('[name="corrected_cost"]').fill('2516.01')
            page.get_by_role('button',name='Выбрать все CD',exact=True).click()
            page.get_by_role('button',name='Распределить текущую неустойку',exact=True).click()
            expect(rows.last.locator('[name="corrected_cost"]')).to_have_value('2456.01')
            expect(page.locator('[data-trip-price-key]')).to_have_count(0)
            page.set_viewport_size({'width':390,'height':844})
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),390)
            expect(rows.last.locator('[name="corrected_cost"]')).to_be_visible()
            page.screenshot(path=str(output/'compact-mobile.png'),full_page=True)
            page.get_by_role('button',name='Подтвердить финализацию рейса',exact=True).click()
            page.wait_for_url(self.live_server_url+reverse('orders:trip_detail',args=[self.trip.pk]))
            from supplies.models import Supply
            supply=Supply.objects.get()
            page.goto(self.live_server_url+reverse('supplies:detail',args=[supply.pk]))
            page.get_by_role('button',name='Проверить цены и принять приход',exact=True).click()
            page.wait_for_url(self.live_server_url+reverse('supplies:price_review',args=[supply.pk]))
            supply.refresh_from_db();self.stock.refresh_from_db()
            self.assertEqual(supply.status,Supply.Status.PRICE_REVIEW_REQUIRED)
            self.assertEqual(self.stock.quantity,5)
            expect(page.locator('[data-wholesale-margin]')).to_have_attribute('data-cost','1201.72')
            page.locator(f'[name="cd_{self.cd.pk}_wholesale_price"]').fill('1600')
            page.locator(f'[name="cd_{self.cd.pk}_avito_price"]').fill('1800')
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(output/'supply-average-price-review.png'),full_page=True)
            page.get_by_role('button',name='Подтвердить цены и поставить на баланс',exact=True).click()
            page.wait_for_url(self.live_server_url+reverse('supplies:detail',args=[supply.pk]))
            self.stock.refresh_from_db();self.cd.refresh_from_db()
            self.assertEqual(self.stock.quantity,7)
            self.assertEqual(str(self.cd.cost),'1201.72')
            self.assertEqual(str(self.cd.wholesale_price),'1600.00')
            self.assertEqual(str(self.cd.avito_price),'1800.00')
            self.assertEqual(errors,[])
            browser.close()
