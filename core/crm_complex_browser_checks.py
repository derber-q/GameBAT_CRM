"""Сквозные проверки новых форм на отдельной SQLite без внешних интеграций."""
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright, expect
from orders import test_trip_additions as addition_fixture
from partners.models import SalesPlatform
from warehouse.models import Warehouse, CDWarehouseStock
from consignment.services import transfer_to_consignment


class CRMComplexBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        addition_fixture.TripAdditionTests.setUp(self)
        self.warehouse=Warehouse.objects.create(name='Браузерный склад')
        self.cd.avito_price=150;self.cd.wholesale_price=130
        self.cd.save(update_fields=('avito_price','wholesale_price'))
        CDWarehouseStock.objects.create(cd=self.cd,warehouse=self.warehouse,quantity=20)
        self.output=Path(settings.BASE_DIR)/'outputs/crm_complex_20261025/browser'
        self.output.mkdir(parents=True,exist_ok=True)

    def context(self,browser,width=1440):
        context=browser.new_context(viewport={'width':width,'height':1000})
        context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
        context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
        return context

    def test_trip_wizard_search_live_cost_distribution_and_commit(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch();context=self.context(browser);page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse('orders:trip_detail',args=(self.batch.pk,)))
            page.get_by_role('link',name='Добавить дополнительные товары').click()
            page.locator('[data-addition-search]').fill('ADD-CD')
            page.locator('.suggestion').first.click()
            page.locator('[name="lines-0-supplier"]').select_option(str(self.supplier.pk))
            page.locator('[name="lines-0-aed"]').fill('110')
            page.locator('[name="lines-0-customer_price"]').fill('2500')
            page.locator('[name="lines-0-stock_qty"]').fill('2')
            page.locator('[name="lines-0-customer_qty"]').fill('3')
            expect(page.locator('[data-addition-cost]')).to_contain_text('Себестоимость 2250.00')
            page.screenshot(path=str(self.output/'additional-step1.png'),full_page=True)
            page.get_by_role('button',name='Продолжить',exact=True).click()
            page.locator(f'[name="partners"][value="{self.partner.pk}"]').check()
            page.locator(f'[name="partners"][value="{self.other.pk}"]').check()
            page.get_by_role('button',name='Продолжить',exact=True).click()
            page.locator(f'[name="0:{self.partner.pk}"]').fill('1')
            page.locator(f'[name="0:{self.other.pk}"]').fill('2')
            expect(page.get_by_role('columnheader',name='На склад',exact=True)).to_have_count(0)
            page.screenshot(path=str(self.output/'additional-distribution.png'),full_page=True)
            page.get_by_role('button',name='Продолжить',exact=True).click()
            expect(page.get_by_role('heading',name='Новые заказы')).to_be_visible()
            page.screenshot(path=str(self.output/'additional-preview.png'),full_page=True)
            page.get_by_role('button',name='Создать заказы и добавить в рейс').click()
            page.wait_for_url('**/trips/*/')
            expect(page.get_by_text('Созданы новые заказы:',exact=False)).to_be_visible()
            self.assertEqual(errors,[]);browser.close()

    def test_supply_codes_saved_before_accept_and_not_requested_again(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch();context=self.context(browser,1280);page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse('supplies:create'))
            page.locator('#supply-lines [name="product_search"]').fill('ADD-CD')
            page.locator('.suggestion').first.click()
            expect(page.get_by_text('Введите CUSA / PPSA диска',exact=False)).to_be_visible()
            prompt=page.locator('.supply-weight-prompt')
            prompt.locator('input').fill('036923, Custom-00001, ppsa00123')
            with page.expect_response(lambda response: response.url.endswith(reverse('supplies:product_codes'))
                    and response.request.method == 'POST') as saved_codes:
                prompt.get_by_role('button',name='Сохранить и добавить').click()
            self.assertEqual(saved_codes.value.json()['cusa_ppsa_code'], '036923, Custom-00001, PPSA-00123')
            expect(prompt).to_be_hidden()
            expect(page.locator('#supply-lines [name="product_id"]')).to_have_value(str(self.cd.pk))
            page.get_by_role('button',name='+ Добавить товар',exact=True).first.click()
            page.locator('#supply-lines [name="product_search"]').last.fill('ADD-CD')
            page.locator('.suggestion').first.click()
            expect(page.locator('.supply-weight-prompt:visible')).to_have_count(0)
            page.screenshot(path=str(self.output/'supply-codes.png'),full_page=True)
            self.assertEqual(errors,[]);browser.close()

    def test_reward_preserves_scroll_url_filters_and_collapsed_platform(self):
        shop=SalesPlatform.objects.create(name='Площадка 1',address='А',legal_entity='ООО',phone_1='1')
        other=SalesPlatform.objects.create(name='Площадка 2',address='А',legal_entity='ООО',phone_1='1')
        stock=transfer_to_consignment(actor=self.user,warehouse_id=self.warehouse.pk,platform_id=shop.pk,
                    product_type='cd',product_id=self.cd.pk,quantity=3,receivable_per_unit=150)
        with sync_playwright() as pw:
            browser=pw.chromium.launch();context=self.context(browser);page=context.new_page()
            page.goto(self.live_server_url+reverse('consignment:list')+'?q=Игра')
            page.locator(f'[aria-controls="consignment-platform-{other.pk}"]').click()
            page.evaluate('document.body.style.minHeight="3000px";window.scrollTo(0,200)')
            url=page.url
            row=page.locator(f'[data-consignment-row="cd-{stock.pk}"]')
            row.locator('[name="receivable_per_unit"]').fill('175')
            row.get_by_role('button',name='Сохранить',exact=True).click()
            expect(row.locator('[name="receivable_per_unit"]')).to_have_value('175.00')
            self.assertEqual(page.url,url)
            expect(page.locator(f'#consignment-platform-{other.pk}')).to_be_hidden()
            expect(page.locator('[name="search"]')).to_have_value('Игра')
            page.screenshot(path=str(self.output/'reward-saved.png'),full_page=True)
            browser.close()
