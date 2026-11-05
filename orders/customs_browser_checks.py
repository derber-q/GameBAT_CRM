"""Chromium: редакция, справочник, отличие количества, обновление и настоящий XLSX."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright,expect
from sales.payment_browser_checks import database_call
from .test_arrival import ArrivalFixture
from .arrival import reduce_received
from .arrival_models import TripArrival
from .customs_models import CustomsGroup,CustomsManifest,CustomsProductDefaults


class CustomsBrowserChecks(ArrivalFixture,StaticLiveServerTestCase):
    def test_create_and_download_before_arrival_without_preliminary_mark(self):
        CustomsGroup.objects.create(name='Игровые диски для PS5',medium='disc',platform=self.cd.platform,
            ru_description='Игровые диски для PS5',updated_by=self.user)
        with ThreadPoolExecutor(max_workers=1) as db,sync_playwright() as pw:
            run=lambda fn:db.submit(database_call,fn).result()
            browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':960})
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.live_server_url+'/') else route.abort())
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse('orders:customs',args=[self.trip.pk]))
            expect(page.get_by_text('Количество по составу рейса:',exact=False)).to_be_visible()
            expect(page.get_by_text('Сначала подтвердите фактическое прибытие рейса.',exact=True)).to_have_count(0)
            self.assertNotIn('Предварительная',page.locator('body').inner_text())
            row=page.locator('[data-customs-row]');expect(row.locator('[data-field=quantity]')).to_have_value('12')
            row.locator('[data-field=en_description]').fill('Video game discs before arrival')
            page.locator('[data-customs-ack]').check()
            with page.expect_download() as download:page.get_by_role('button',name='Скачать Excel',exact=True).click()
            output=Path(settings.BASE_DIR)/'outputs/customs_manifest_20261103/browser';output.mkdir(parents=True,exist_ok=True)
            target=output/'before-arrival.xlsx';download.value.save_as(str(target))
            sheet=load_workbook(target).active;self.assertEqual(sheet['I6'].value,12)
            self.assertFalse(any('Предварительная' in str(c.value) for row in sheet for c in row))
            self.assertEqual(run(lambda:CustomsManifest.objects.get(trip=self.trip).source_kind),'planned')
            self.assertFalse(run(lambda:TripArrival.objects.filter(trip=self.trip).exists()))
            page.reload();expect(row.locator('[data-field=en_description]')).to_have_value('Video game discs before arrival')
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':960})
                page.wait_for_function('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(output/f'before-arrival-{width}.png'),full_page=True)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                page.screenshot(path=str(output/f'before-arrival-{width}.png'),full_page=True)
            self.assertEqual(errors,[]);browser.close()

    def test_editor_download_refresh_and_phone(self):
        arrival=self.arrive()
        for order in (self.order,self.stock_order):
            row=arrival.rows.get(order=order)
            reduce_received(actor=self.user,arrival_id=arrival.pk,order_id=order.pk,
                quantities={row.pk:row.actual_quantity},expected_revision=arrival.revision)
            arrival.refresh_from_db()
        CustomsGroup.objects.create(name='Игровые диски для PS5',medium='disc',platform=self.cd.platform,
            ru_description='Игровые диски для PS5',updated_by=self.user)
        output=Path(settings.BASE_DIR)/'outputs/customs_manifest_20261103/browser';output.mkdir(parents=True,exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as db,sync_playwright() as pw:
            run=lambda fn:db.submit(database_call,fn).result()
            browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':960})
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.live_server_url+'/') else route.abort())
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse('orders:trip_detail',args=[self.trip.pk]))
            page.get_by_role('link',name='Таможенная опись',exact=True).click()
            row=page.locator('[data-customs-row]');expect(row).to_have_count(1)
            expect(row.locator('[data-field=country]')).to_have_value('AUSTRIA')
            expect(row.locator('[data-field=quantity]')).to_have_value('12')
            row.locator('[data-field=quantity]').fill('9007199254740993')
            self.assertEqual(''.join(page.locator('[data-customs-total]').inner_text().split()),'9007199254740993')
            row.locator('[data-field=quantity]').fill('12')
            for field,value in [('ru_description','Диски PS5 — проверенный состав'),('en_description','Video game discs for PlayStation 5'),
                ('country','JAPAN'),('manufacturer','TEST MAKER'),('hs_code','0123456789'),('marking','=TEST_LITERAL')]:
                row.locator(f'[data-field={field}]').fill(value)
            row.locator('[data-confirm-row]').check()
            page.get_by_role('button',name='Сохранить изменения',exact=True).click()
            expect(page.locator('[data-customs-message]')).to_contain_text('Сохранена редакция 1')
            page.reload();expect(row.locator('[data-field=hs_code]')).to_have_value('0123456789')
            expect(row.locator('[data-field=en_description]')).to_have_value('Video game discs for PlayStation 5')
            page.once('dialog',lambda dialog:dialog.accept())
            row.get_by_role('button',name='Сохранить для товара',exact=True).click()
            expect(page.locator('[data-customs-message]')).to_contain_text('для будущих рейсов')
            self.assertEqual(run(lambda:CustomsProductDefaults.objects.get(cd=self.cd).country),'JAPAN')
            row.locator('[data-field=quantity]').fill('11')
            page.get_by_role('button',name='Сохранить изменения',exact=True).click()
            expect(page.locator('[data-customs-message]')).to_contain_text('подтверждения')
            expect(row.locator('[data-field=quantity]')).to_have_value('11')
            row.locator('[data-quantity-reason]').fill('Проверенная корректировка только таможенного документа')
            row.locator('[data-quantity-confirmed]').check()
            page.get_by_role('button',name='Сохранить изменения',exact=True).click()
            expect(page.locator('[data-customs-message]')).to_contain_text('Сохранена редакция 2')
            def change_actual():
                actual=TripArrival.objects.get(pk=arrival.pk);source=actual.rows.get(order=self.order)
                reduce_received(actor=self.user,arrival_id=actual.pk,order_id=self.order.pk,
                    quantities={source.pk:8},expected_revision=actual.revision)
            run(change_actual)
            page.reload();expect(page.get_by_text('Фактический состав рейса изменился после подготовки таможенной описи.',exact=False)).to_be_visible()
            expect(page.get_by_role('button',name='Скачать Excel',exact=True)).to_be_disabled()
            row.locator('[data-field=en_description]').fill('Video game discs — refreshed')
            row.locator('[data-confirm-row]').check()
            page.once('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='Обновить по фактическому составу',exact=True).click()
            expect(page.locator('[data-customs-revision]')).to_have_text('3')
            expect(row.locator('[data-field=en_description]')).to_have_value('Video game discs — refreshed')
            expect(row.locator('[data-field=quantity]')).to_have_value('10')
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':960});row.locator('[data-field=en_description]').scroll_into_view_if_needed()
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                page.screenshot(path=str(output/f'editor-{width}.png'),full_page=True)
            page.locator('[data-customs-ack]').check()
            with page.expect_download() as download:
                page.get_by_role('button',name='Скачать Excel',exact=True).click()
            target=output/'download.xlsx';download.value.save_as(str(target))
            sheet=load_workbook(target).active
            self.assertEqual((sheet['I6'].value,sheet['G6'].value),(10,'JAPAN'))
            self.assertEqual(sheet['C6'].value,'=TEST_LITERAL');self.assertEqual(sheet['C6'].data_type,'s')
            self.assertEqual(sheet['E6'].value,'Video game discs — refreshed')
            self.assertEqual(run(lambda:TripArrival.objects.get(pk=arrival.pk).rows.get(order=self.order).actual_quantity),8)
            self.assertEqual(run(lambda:CustomsManifest.objects.filter(trip=self.trip).count()),4)
            self.assertEqual(errors,[]);browser.close()
