"""Полный браузерный путь ручной AED до складского заказа, только искусственная БД."""
from pathlib import Path
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect
from accounts.models import User
from catalog.models import CD, Platform, Brand, ProductType, Tech
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice
from orders.models import CustomerProcurementOrder
from sales.payment_browser_checks import database_call
from .services import create_procurement_price_list


class ProcurementManualBrowserChecks(StaticLiveServerTestCase):
    def test_manual_drafts_validation_reload_stock_order_and_phone(self):
        actor=User.objects.create_superuser('manual-browser-owner')
        self.client.force_login(actor)
        cd=CD.objects.create(name='Тестовая игра AED',platform=Platform.objects.create(name='PS5'),sku='MANUAL-CD')
        tech=Tech.objects.create(name='Тестовый геймпад',brand=Brand.objects.create(name='Sony'),
            product_type=ProductType.objects.create(name='Геймпады'),weight_grams=1000,sku='MANUAL-TECH')
        suppliers={}
        for letter,price in [('A',10),('F',15),('M',9)]:
            supplier=Supplier.objects.create(name='Поставщик '+letter,letter=letter,highlight_color='#37A7BA',legal_entity=letter,phone_1='1')
            suppliers[letter]=supplier
            SupplierCDPrice.objects.create(supplier=supplier,cd=cd,price=price)
            SupplierTechPrice.objects.create(supplier=supplier,tech=tech,price=price*10)
        price=create_procurement_price_list(actor=actor,exchange_rate_usdt_aed='3.67',exchange_rate_usdt_rub=90,
            delivery_general_usdt_per_kg=0,delivery_devices_usdt_per_kg=0,delivery_storage_usdt_per_kg=0,
            delivery_cd_rub=5,postpayment_surcharges={tech.pk:125})
        item=price.items.get(cd=cd)
        output=Path(settings.BASE_DIR)/'outputs/procurement_manual_20261103/browser';output.mkdir(parents=True,exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as db,sync_playwright() as pw:
            run=lambda fn:db.submit(database_call,fn).result()
            browser=pw.chromium.launch()
            context=browser.new_context(viewport={'width':1440,'height':960})
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.live_server_url+'/') else route.abort())
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            url=self.live_server_url+reverse('price:procurement_detail',args=[price.pk])
            page.goto(url)
            row=page.locator(f'[data-item-id="{item.pk}"]')
            picker=row.locator('[data-supplier-select]');toggle=row.locator('[data-manual-price-toggle]');aed=row.locator('[data-manual-price]')
            expect(toggle).not_to_be_checked();expect(aed).to_be_hidden()
            picker.select_option(str(suppliers['A'].pk));toggle.check();expect(aed).to_have_value('10.000000')
            row.locator('[data-markup]').fill('123.45')
            aed.fill('');expect(row.locator('[data-price-error]')).not_to_be_empty()
            aed.press_sequentially('12.50')
            expect(row.locator('[data-total-cost-display]')).to_have_text('311.54')
            expect(row.locator('[data-prepayment]')).to_have_value('440.00')
            expect(row.locator('[data-postpayment]')).to_have_value('500.00')
            expect(row.locator('[data-markup]')).to_have_value('123.45')
            picker.select_option(str(suppliers['F'].pk));expect(toggle).not_to_be_checked()
            toggle.check();aed.fill('20')
            picker.select_option(str(suppliers['M'].pk));expect(toggle).not_to_be_checked()
            picker.select_option(str(suppliers['A'].pk));expect(toggle).to_be_checked();expect(aed).to_have_value('12.50')
            expect(row.locator(f'[data-supplier-id="{suppliers["F"].pk}"]')).to_have_class('procurement-supplier-offer is-expensive')
            aed.fill('1e3');page.get_by_role('button',name='Сохранить расчёт',exact=True).click()
            expect(aed).to_have_value('1e3');expect(row.locator('[data-price-error]')).not_to_be_empty()
            aed.fill('12.50');page.get_by_role('button',name='Сохранить расчёт',exact=True).click()
            expect(aed).to_have_value('12.500000');expect(toggle).to_be_checked()
            expect(row.locator('.is-selected')).to_have_text('A–12.5 ✎')
            self.assertEqual(run(lambda:price.items.get(cd=cd).supplier_offers.get(supplier=suppliers['A']).price_aed),Decimal('10'))
            # Снятие флажка восстанавливает исходное предложение и переживает сохранение.
            toggle.uncheck();expect(row.locator('[data-total-cost-display]')).to_have_text('250.23')
            page.get_by_role('button',name='Сохранить расчёт',exact=True).click();expect(toggle).not_to_be_checked()
            toggle.check();aed.fill('12.50');page.get_by_role('button',name='Сохранить расчёт',exact=True).click()
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':960});page.goto(url)
                expect(toggle).to_be_checked();expect(aed).to_have_value('12.500000')
                if width == 390:
                    aed.scroll_into_view_if_needed()
                    aed.fill('12.500001')
                    expect(row.locator('[data-prepayment]')).to_have_value('440.00')
                    aed.fill('12.500000')
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                page.screenshot(path=str(output/f'editor-{width}.png'),full_page=True)
                page.goto(self.live_server_url+reverse('orders:stock_create')+f'?price_list={price.pk}')
                stock=page.locator('[data-stock-order-row]').filter(has=page.locator(f'[name="quantity_{item.pk}"]'))
                expect(stock.locator('.is-selected')).to_have_text('A–12.5 ✎')
                expect(stock.locator('[title^="Ручная цена."]').first).to_be_visible()
                page.locator(f'[name="quantity_{item.pk}"]').fill('2')
                expect(page.locator('[data-stock-order-total]')).to_have_text('623,08')
                page.locator('[data-stock-order-search]').fill('MANUAL-CD')
                expect(page.locator('[data-stock-order-row]:visible')).to_have_count(1)
                expect(page.locator('[data-stock-order-units]')).to_have_text('2')
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                page.screenshot(path=str(output/f'stock-{width}.png'),full_page=True)
            page.get_by_role('button',name='Проверить и показать состав',exact=True).click()
            page.get_by_role('button',name='Создать заказ',exact=True).click()
            ordered=run(lambda:CustomerProcurementOrder.objects.get(price_list=price).items.get().supplier_price_aed_snapshot)
            self.assertEqual(ordered,Decimal('12.50'))
            page.goto(url);expect(page.get_by_role('button',name='Сохранить расчёт',exact=True)).to_have_count(0)
            from catalog.supplier_exclusions import set_supplier_exclusions
            run(lambda:set_supplier_exclusions(product=cd,supplier_ids=[suppliers['F'].pk],actor=actor))
            page.goto(self.live_server_url+reverse('orders:stock_create')+f'?price_list={price.pk}')
            excluded=page.locator('[data-stock-order-row]').filter(has=page.locator(
                f'[name="quantity_{item.pk}"]')).locator(f'[data-supplier-id="{suppliers["F"].pk}"]')
            expect(excluded).to_have_css('color','rgb(100, 116, 139)')
            expect(excluded).to_have_css('text-decoration-line','line-through')
            page.screenshot(path=str(output/'stock-excluded-390.png'),full_page=True)
            self.assertEqual(errors,[])
            browser.close()
