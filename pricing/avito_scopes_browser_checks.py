"""Настоящее MV3-расширение: CD/Tech с одинаковым ID и независимыми географиями."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Tech, Platform, Brand, ProductType
from integrations.models import AvitoProductProfile, AvitoRemoteListing, AvitoListingConnection, AvitoManualPrice
from sales.payment_browser_checks import database_call
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock
from .avito_extension_browser_checks import AVITO_RESULTS


class AvitoScopesBrowserChecks(StaticLiveServerTestCase):
    def test_mixed_queue_scope_prefill_conflict_tech_save_and_clicked_start(self):
        actor=User.objects.create_superuser('mixed-scope-browser')
        warehouse=Warehouse.objects.create(name='Общий склад браузера')
        cd=CD.objects.create(name='A Browser disc',platform=Platform.objects.create(name='PlayStation 5'),
            cost=500,wholesale_price=1200,avito_price=1500)
        tech=Tech.objects.create(pk=cd.pk,name='B Browser DualSense',brand=Brand.objects.create(name='Sony'),
            product_type=ProductType.objects.create(name='Геймпады'),cost=700,wholesale_price=1700,avito_price=1900)
        CDWarehouseStock.objects.create(cd=cd,warehouse=warehouse,quantity=2)
        TechWarehouseStock.objects.create(tech=tech,warehouse=warehouse,quantity=3)
        for index,product in enumerate([cd,tech],1):
            profile=AvitoProductProfile.objects.create(**{product._meta.model_name:product})
            AvitoListingConnection.objects.create(profile=profile,
                remote_listing=AvitoRemoteListing.objects.create(avito_item_id=9000+index))
            AvitoManualPrice.objects.create(profile=profile,price=1000 if index==1 else 1600,
                scope='russia',recorded_at=timezone.now(),recorded_by=actor)
        self.client.force_login(actor)
        output=Path(settings.BASE_DIR)/'outputs/avito_scopes_20261103/browser'
        output.mkdir(parents=True,exist_ok=True)
        extension=Path(settings.BASE_DIR)/'browser_extensions/avito_check'
        with ThreadPoolExecutor(max_workers=1) as db,TemporaryDirectory(ignore_cleanup_errors=True) as profile_dir,sync_playwright() as pw:
            run=lambda callback:db.submit(database_call,callback).result()
            context=pw.chromium.launch_persistent_context(profile_dir,channel='chromium',headless=True,
                viewport={'width':1440,'height':950},args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}'])
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('https://www.avito.ru/**',lambda route:route.fulfill(content_type='text/html',body=AVITO_RESULTS))
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            errors=[]
            context.on('page',lambda page:page.on('pageerror',lambda error:errors.append(str(error))))
            page=context.new_page()
            with patch('integrations.avito_check.ReefApiClient') as paid:
                page.goto(self.live_server_url+reverse('pricing:avito_check'))
                expect(page.locator('html')).to_have_attribute('data-resource-avito-connected','1')
                row=lambda kind:page.locator(f'tr[data-found-price-row][data-kind="{kind}"][data-product-id="{cd.pk}"]')
                cell=lambda kind,scope:row(kind).locator(f'[data-scope-cell="{scope}"]')
                with context.expect_page() as opened:
                    cell('cd','russia').get_by_role('link',name='Поиск · РФ').click()
                avito=opened.value
                panel=avito.locator('resource-avito-check')
                field=panel.get_by_label('Минимальная цена, ₽')
                expect(field).to_have_value('1000.00')
                expect(panel.locator('[data-product-scope]')).to_have_text('Диск · Россия')
                field.fill('1100')
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.locator('[data-product-scope]')).to_have_text('Диск · Ростов-на-Дону')
                expect(field).to_have_value('')
                self.assertIn('/rostov-na-donu/',avito.url)
                expect(cell('cd','russia').locator('[name="price"]')).to_have_value('1100.00')
                expect(cell('tech','russia').locator('[name="price"]')).to_have_value('1600.00')
                expect(cell('cd','rostov').locator('[name="price"]')).to_have_value('')
                # Изменение РФ в другой вкладке не создаёт конфликт для Ростова.
                def elsewhere(scope,amount):
                    record=AvitoManualPrice.objects.get(profile__cd=cd,scope=scope)
                    record.price,record.recorded_at=Decimal(amount),timezone.now()
                    record.save(update_fields=('price','recorded_at'))
                run(lambda:elsewhere('russia','1150'))
                field.fill('900')
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.locator('[data-product-scope]')).to_have_text('Техника · Россия')
                expect(field).to_have_value('1600.00')
                self.assertIn('/all?',avito.url)
                self.assertNotIn('f=',avito.url)
                expect(row('cd').locator('[data-scope-warning]')).to_be_visible()
                field.fill('1650')
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.locator('[data-product-scope]')).to_have_text('Техника · Ростов-на-Дону')
                expect(field).to_have_value('')
                avito.reload()
                expect(panel.locator('[data-product-scope]')).to_have_text('Техника · Ростов-на-Дону')
                expect(field).to_have_value('')
                field.fill('1700')
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel).to_have_attribute('data-state','done')
                self.assertEqual(run(lambda:dict(AvitoManualPrice.objects.filter(profile__tech=tech).values_list('scope','price'))),
                    {'russia':Decimal('1650'),'rostov':Decimal('1700')})
                # Начало из Ростова не перепрыгивает на первый товар/РФ.
                with context.expect_page() as opened_city:
                    cell('cd','rostov').get_by_role('link',name='Поиск · Ростов').click()
                city=opened_city.value
                city_panel=city.locator('resource-avito-check')
                city_field=city_panel.get_by_label('Минимальная цена, ₽')
                expect(city_panel.locator('[data-product-scope]')).to_have_text('Диск · Ростов-на-Дону')
                expect(city_field).to_have_value('900.00')
                run(lambda:elsewhere('rostov','950'))
                city_field.fill('920')
                city_panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(city_panel.get_by_role('alert')).to_contain_text('уже изменена')
                city_panel.get_by_role('button',name='Обновить панель').click()
                expect(city_field).to_have_value('950.00')
                # Обычный AJAX после extension-save использует обновлённую версию РФ.
                rf=cell('tech','russia')
                rf.locator('[name="price"]').fill('1660')
                rf.get_by_role('button',name='Сохранить',exact=True).click()
                expect(rf.locator('[data-save-status]')).to_have_text('Сохранено')
                for width in (1440,768,390):
                    page.set_viewport_size({'width':width,'height':950})
                    page.locator('.table-scroll').evaluate('(element) => {element.scrollLeft=0;}')
                    page.screenshot(path=str(output/f'table-{width}.png'),full_page=True)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                    expect(cell('tech','rostov').locator('[name="price"]')).to_have_value('1700.00')
                self.assertEqual(run(lambda:Tech.objects.get(pk=tech.pk).avito_price),Decimal('1900'))
                self.assertEqual(errors,[])
                paid.assert_not_called()
            context.close()
