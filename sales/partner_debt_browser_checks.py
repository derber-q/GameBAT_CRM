"""Создание продаж в долг обоими способами через реальную форму Chromium."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import Partner
from warehouse.models import Warehouse, CDWarehouseStock
from .models import Sale
from .payment_browser_checks import database_call


class PartnerDebtBrowserChecks(StaticLiveServerTestCase):
    def test_choose_partner_for_existing_unbound_sale_from_detail_and_list(self):
        from .services import create_sale, cancel_sale, advance_order_status
        actor = User.objects.create_superuser('unbound-debt-browser')
        partner = Partner.objects.create(name='Zona61')
        warehouse = Warehouse.objects.create(name='Склад выбора партнёра')
        product = CD.objects.create(name='Игра с частичной оплатой', platform=Platform.objects.create(name='PS5'),
            wholesale_price='35300', avito_price='36000', cost='10000')
        stock = CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/payment-partner-browser'
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for source in ('detail', 'list'):
                sale = run(lambda: create_sale(actor=actor, warehouse_id=warehouse.pk, sale_type='wholesale',
                    price_type='wholesale', partner_name='Zona 61', payment_method='cash_postpay',
                    lines=[{'product_type': 'cd', 'product_id': product.pk, 'quantity': 1}]))
                for status in ('assembled', 'delivered'):
                    run(lambda: advance_order_status(actor=actor, sale_id=sale.pk, next_status=status))
                if source == 'detail':
                    page.goto(self.live_server_url + reverse('sales:detail', args=[sale.pk]))
                    choice = page.locator('#sale-payment-partner')
                    received = page.locator('#cash-received-at-payment')
                    button = page.get_by_role('button', name='Отметить как оплаченную', exact=True)
                else:
                    page.goto(self.live_server_url + reverse('sales:incomplete'))
                    page.locator(f'[data-sale-row="{sale.pk}"] [data-status-field="payment"]').select_option('paid')
                    choice = page.locator('#sale-status-partner')
                    received = page.locator('#sale-status-cash')
                    button = page.locator('#sale-status-confirm-form button[type="submit"]')
                expect(choice).to_be_visible()
                expect(received).to_have_attribute('min', '35300.00')
                choice.select_option(str(partner.pk))
                expect(received).to_have_attribute('min', '0')
                received.fill('30000')
                button.click()
                confirmation = page.get_by_role('dialog').filter(has=page.locator('[data-summary]'))
                expect(confirmation).to_be_visible()
                expect(confirmation.locator('[data-summary]')).to_contain_text('5 300,00 ₽')
                self.assertIsNone(run(lambda: Sale.objects.get(pk=sale.pk).partner_id))
                confirmation.get_by_role('button', name='Отмена', exact=True).click()
                self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), 0)
                button.click()
                expect(confirmation).to_be_visible()
                confirmation.locator('[data-note]').fill('Остаток 5300 в долг')
                page.screenshot(path=str(output / f'{source}-confirmation.png'), full_page=True)
                confirmation.get_by_role('button', name='Подтвердить расчёт', exact=True).click()
                if source == 'detail':
                    expect(page.get_by_text('Частично оплачено, остаток в долг', exact=True)).to_be_visible()
                else:
                    expect(page.locator(f'[data-sale-row="{sale.pk}"]')).to_have_count(0)
                    expect(page.locator('#sales-status-message')).to_contain_text('Статус сохранён')
                paid = run(lambda: Sale.objects.get(pk=sale.pk))
                self.assertEqual((paid.partner_id, paid.cash_received_amount, paid.debt_charge_amount),
                    (partner.pk, 30000, 5300))
                self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), 5300)
                self.assertEqual(run(lambda: Warehouse.objects.get(pk=warehouse.pk).cash_register.balance), 30000)
                run(lambda: cancel_sale(actor=actor, sale_id=sale.pk, comment='Возврат'))
                self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), 0)
                self.assertEqual(run(lambda: Warehouse.objects.get(pk=warehouse.pk).cash_register.balance), 0)
                self.assertEqual(run(lambda: CDWarehouseStock.objects.get(pk=stock.pk).quantity), 10)
            self.assertEqual(errors, [])
            browser.close()

    def test_existing_sale_partial_payment_confirmation_and_cancellation(self):
        from .services import create_sale
        actor = User.objects.create_superuser('partial-debt-browser')
        partner = Partner.objects.create(name='Партнёр частичной оплаты')
        warehouse = Warehouse.objects.create(name='Склад частичной оплаты')
        product = CD.objects.create(name='Частичная оплата', platform=Platform.objects.create(name='PS5'),
            wholesale_price='65900', avito_price='70000', cost='40000')
        stock = CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        sale = create_sale(actor=actor, warehouse_id=warehouse.pk, sale_type='wholesale', price_type='wholesale',
            partner_id=partner.pk, payment_method='cash_postpay',
            lines=[{'product_type':'cd','product_id':product.pk,'quantity':1}])
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/partner_partial_20261025/browser'
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width':1440,'height':1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page = context.new_page()
            errors = []
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url + reverse('sales:detail',args=[sale.pk]))
            page.locator('#cash-received-at-payment').fill('52900')
            page.get_by_role('button',name='Отметить как оплаченную',exact=True).click()
            dialog = page.get_by_role('dialog').filter(has=page.locator('[data-summary]'))
            expect(dialog).to_be_visible()
            expect(dialog.locator('[data-summary]')).to_contain_text('Начислено в долг партнёру')
            expect(dialog.locator('[data-summary]')).to_contain_text('13 000,00 ₽')
            self.assertEqual(run(lambda:partner.creditor.__class__.objects.get(pk=partner.creditor_id).current_debt),0)
            dialog.locator('[data-note]').fill('Остаток 13000 в долг')
            page.screenshot(path=str(output/'confirmation.png'),full_page=True)
            dialog.get_by_role('button',name='Подтвердить расчёт').click()
            expect(page.get_by_text('Частично оплачено, остаток в долг',exact=True)).to_be_visible()
            expect(page.get_by_text('Начислено в долг партнёру',exact=True)).to_be_visible()
            self.assertEqual(run(lambda:Sale.objects.get(pk=sale.pk).debt_charge_amount),13000)
            self.assertEqual(run(lambda:Warehouse.objects.get(pk=warehouse.pk).cash_register.balance),52900)
            page.screenshot(path=str(output/'paid.png'),full_page=True)
            page.get_by_role('button',name='Отменить продажу',exact=True).click()
            cancel = page.locator('#sale-cancel-dialog')
            expect(cancel).to_be_visible()
            cancel.locator('[name="cancellation_comment"]').fill('Возврат товара')
            cancel.get_by_role('button',name='Да, отменить продажу',exact=True).click()
            expect(page.get_by_text('Продажа отменена',exact=False).first).to_be_visible()
            self.assertEqual(run(lambda:CDWarehouseStock.objects.get(pk=stock.pk).quantity),10)
            self.assertEqual(run(lambda:Warehouse.objects.get(pk=warehouse.pk).cash_register.balance),0)
            self.assertEqual(run(lambda:partner.creditor.__class__.objects.get(pk=partner.creditor_id).current_debt),0)
            self.assertEqual(errors,[])
            browser.close()

    def test_debt_option_and_cash_zero_create_debt_without_cash(self):
        actor = User.objects.create_superuser('debt-browser')
        partner = Partner.objects.create(name='Игромир')
        warehouse = Warehouse.objects.create(name='Склад проверки')
        product = CD.objects.create(name='Игра для партнёра', platform=Platform.objects.create(name='PS5'),
            wholesale_price='10000.25', avito_price='11000', cost='6000', barcode='000000123456')
        CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/partner_debt_20261023/browser'
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            for index, method in enumerate(('partner_debt', 'cash'), start=1):
                page.goto(self.live_server_url + reverse('sales:create'))
                option = page.locator('#id_payment_method option[value="partner_debt"]')
                expect(option).to_be_disabled()
                page.locator('#id_sale_type').select_option('wholesale')
                expect(option).to_be_disabled()
                page.locator('#id_customer').select_option(str(partner.pk))
                expect(option).to_be_enabled()
                page.locator('#id_payment_method').select_option('partner_debt')
                page.locator('#id_customer').select_option('custom')
                expect(page.locator('#id_payment_method')).to_have_value('cash')
                expect(option).to_be_disabled()
                page.locator('#id_customer').select_option(str(partner.pk))
                page.locator('#id_warehouse').select_option(str(warehouse.pk))
                page.locator('[data-sale-barcode-input]').fill('000000123456')
                page.locator('[data-sale-barcode-input]').press('Enter')
                expect(page.locator('[data-sale-intermediate-total]')).to_have_text('10 000,25 ₽')
                page.locator('#id_payment_method').select_option(method)
                if method == 'cash':
                    page.locator('#id_cash_received_amount').fill('0')
                else:
                    expect(page.locator('#id_cash_received_amount')).to_be_disabled()
                    expect(page.locator('[data-payment-workflow]')).to_contain_text('увеличит долг партнёра')
                page.screenshot(path=str(output / f'{method}.png'), full_page=True)
                page.get_by_role('button', name='Продажа выполнена', exact=True).click()
                try:
                    page.wait_for_url(re.compile(r'/sales/\d+/$'), timeout=10000)
                except Exception:
                    page.screenshot(path=str(output / 'failure.png'), full_page=True)
                    print('Текущий URL:', page.url, 'Ошибки JS:', errors)
                    print(page.locator('main').inner_text()[:2500])
                    raise
                expect(page.get_by_text('Начислено в долг партнёру', exact=True)).to_be_visible()
                sale = run(lambda: Sale.objects.latest('pk'))
                self.assertEqual((sale.payment_method, sale.cash_received_amount), ('partner_debt', 0))
                self.assertFalse(run(lambda: sale.cash_transactions.exists()))
                self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), sale.total_amount * index)
                self.assertEqual(run(lambda: Warehouse.objects.get(pk=warehouse.pk).cash_register.balance), 0)
            # Полная оплата выбранному партнёру также отправляется без лишнего диалога.
            page.goto(self.live_server_url + reverse('sales:create'))
            page.locator('#id_sale_type').select_option('wholesale')
            page.locator('#id_customer').select_option(str(partner.pk))
            page.locator('#id_warehouse').select_option(str(warehouse.pk))
            page.locator('[data-sale-barcode-input]').fill('000000123456')
            page.locator('[data-sale-barcode-input]').press('Enter')
            expect(page.locator('[data-sale-intermediate-total]')).to_have_text('10 000,25 ₽')
            page.locator('#id_cash_received_amount').fill('10000.25')
            page.get_by_role('button', name='Продажа выполнена', exact=True).click()
            page.wait_for_url(re.compile(r'/sales/\d+/$'))
            self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), sale.total_amount * 2)
            self.assertEqual(run(lambda: Warehouse.objects.get(pk=warehouse.pk).cash_register.balance), sale.total_amount)
            self.assertEqual(errors, [])
            browser.close()
