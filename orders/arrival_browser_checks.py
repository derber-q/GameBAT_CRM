"""Полный цикл рейса в Chromium на отдельной тестовой БД."""
import os
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect
from .test_arrival import ArrivalFixture
from .arrival_models import TripArrival
from sales.models import Sale
from supplies.models import Supply


class ArrivalBrowserChecks(ArrivalFixture, StaticLiveServerTestCase):
    @patch.dict(os.environ,{'DJANGO_ALLOW_ASYNC_UNSAFE':'true'})
    def test_arrival_mixed_sale_supply_joint_finalization_and_posting(self):
        output=Path(settings.BASE_DIR)/'outputs/trip_arrival_20261026/browser';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw, closing(connections['default']):
            browser=pw.chromium.launch(); context=browser.new_context(viewport={'width':1440,'height':1000})
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            trip_url=self.live_server_url+reverse('orders:trip_detail',args=[self.trip.pk])
            page.goto(trip_url)
            form=page.locator('[data-trip-arrival-form]')
            form.locator('[name="actual_delivery"]').fill('1200')
            form.locator('[name="usdt_aed"]').fill('3.66')
            form.locator('[name="usdt_rub"]').fill('88.06')
            form.get_by_role('button',name='Предварительный расчёт',exact=True).click()
            expect(page.locator('#trip-arrival')).to_contain_text('30072.12')
            self.assertFalse(TripArrival.objects.exists())
            page.screenshot(path=str(output/'arrival-preview.png'),full_page=True)
            page.get_by_role('button',name='Рейс приехал',exact=True).click()
            expect(page.locator('[data-trip-arrival-form]')).to_have_count(0)
            page.goto(self.live_server_url+reverse('orders:operation_prepare',args=[self.order.pk]))
            page.wait_for_url('**/sales/new/?trip_draft=*')
            expect(page.locator('[name="usd_rub"]')).to_have_count(0)
            expect(page.locator('[data-game-codes]').first).to_have_text('PPSA-00001')
            page.locator('.stock-lines [name="quantity"]').fill('8')
            page.locator('.add-stock-line').first.click()
            page.locator('[data-product-search]').last.fill('FX-CD')
            page.locator('.suggestion').filter(has_text='Игра').first.click()
            page.locator('.stock-lines [name="quantity"]').last.fill('2')
            page.get_by_role('button',name='Создать продажу',exact=True).click()
            expect(page.get_by_role('heading',name='Подтвердить изменения заказа?',exact=True)).to_be_visible()
            self.assertFalse(Sale.objects.exists())
            page.get_by_role('button',name='Подтвердить изменения и создать',exact=True).click()
            page.wait_for_url('**/sales/*/')
            self.stock.refresh_from_db(); self.assertEqual(self.stock.quantity,3)
            self.assertEqual(Sale.objects.get().total_amount,Decimal('47998'))
            page.goto(self.live_server_url+reverse('orders:operation_prepare',args=[self.stock_order.pk]))
            if page.locator('h1').inner_text()=='Проверка товаров':
                page.get_by_role('button',name='Продолжить к приходу',exact=True).click()
            page.wait_for_url('**/supplies/new/?trip_draft=*')
            expect(page.locator('#supply-lines [name="purchase_unit_cost"]')).to_have_value('2526.01')
            expect(page.locator('.supply-weight-prompt:visible')).to_have_count(0)
            page.get_by_role('button',name='Сохранить сверку рейса',exact=True).click()
            page.wait_for_url('**/supplies/*/')
            self.assertEqual(Supply.objects.get().status,Supply.Status.WAITING_TRIP_FINALIZATION)
            page.goto(trip_url)
            page.get_by_role('link',name='Итоговая финализация рейса',exact=True).click()
            rows=page.locator('.finalization-row')
            expect(rows).to_have_count(2)
            rows.first.locator('[name="corrected_cost"]').fill('2536.01')
            page.get_by_role('button',name='Выбрать все CD',exact=True).click()
            page.get_by_role('button',name='Распределить текущую неустойку',exact=True).click()
            expect(rows.last.locator('[name="corrected_cost"]')).to_have_value('2486.01')
            expect(page.locator('[data-trip-price-key]')).to_have_count(0)
            page.screenshot(path=str(output/'joint-finalization.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            expect(page.get_by_role('button',name='Подтвердить финализацию рейса',exact=True)).to_be_visible()
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),390)
            page.screenshot(path=str(output/'joint-finalization-mobile.png'),full_page=True)
            page.get_by_role('button',name='Подтвердить финализацию рейса',exact=True).click()
            page.wait_for_url(trip_url)
            self.cd.refresh_from_db(); self.assertEqual(self.cd.wholesale_price,Decimal('9999'))
            supply=Supply.objects.get()
            page.goto(self.live_server_url+reverse('supplies:detail',args=[supply.pk]))
            page.get_by_role('button',name='Проверить цены и принять приход',exact=True).click()
            page.wait_for_url('**/supplies/*/price-review/')
            supply.refresh_from_db();self.assertEqual(supply.status,Supply.Status.PRICE_REVIEW_REQUIRED)
            page.locator(f'[name="cd_{self.cd.pk}_wholesale_price"]').fill('4800')
            page.locator(f'[name="cd_{self.cd.pk}_avito_price"]').fill('5000')
            page.get_by_role('button',name='Подтвердить цены и поставить на баланс',exact=True).click()
            expect(page.get_by_role('heading',name='Ждёт финализации рейса',exact=True)).to_have_count(0)
            supply.refresh_from_db(); self.stock.refresh_from_db(); self.cd.refresh_from_db()
            self.assertEqual(supply.status,Supply.Status.ACCEPTED)
            self.assertEqual(self.stock.quantity,5)
            self.assertEqual(self.cd.wholesale_price,Decimal('4800'))
            self.assertEqual(self.cd.avito_price,Decimal('5000'))
            self.assertEqual(errors,[])
            browser.close()
