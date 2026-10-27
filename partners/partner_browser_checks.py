"""Полный путь оптовой продажи с подтверждением взаимозачёта в Chromium."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright
from django.urls import reverse
from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from creditors.services import adjust_creditor_debt
from sales.models import Sale
from sales.payment_browser_checks import database_call
from .models import Partner


class PartnerBrowserChecks(StaticLiveServerTestCase):
    def test_postpayment_from_list_confirms_repayment_and_leaves_bank_out_of_cash(self):
        from sales.services import create_sale, advance_order_status
        actor = User.objects.create_superuser('partner-postpay-browser')
        warehouse = Warehouse.objects.create(name='Склад постоплаты')
        partner = Partner.objects.create(name='Постоплатный партнёр')
        adjust_creditor_debt(actor=actor, creditor_id=partner.creditor_id, warehouse_id=warehouse.pk,
            money_source_type='offset', new_debt='3000', comment='Начальный долг')
        sale = create_sale(actor=actor, warehouse_id=warehouse.pk, price_type='wholesale', sale_type='wholesale',
            payment_method='bank_transfer_postpay', partner_id=partner.pk,
            lines=[{'product_type': 'custom', 'name': 'Товар', 'quantity': 1, 'unit_price': '10000', 'unit_cost': '6000'}])
        advance_order_status(actor=actor, sale_id=sale.pk, next_status='assembled')
        advance_order_status(actor=actor, sale_id=sale.pk, next_status='delivered')
        self.client.force_login(actor)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            page.goto(self.live_server_url + reverse('sales:incomplete'))
            toggle = page.locator('[aria-controls="sales-group-wholesale"]')
            if toggle.get_attribute('aria-expanded') == 'false': toggle.click()
            row = page.locator(f'[data-sale-row="{sale.pk}"]')
            row.locator('[data-status-field="payment"]').select_option('paid')
            page.locator('#sale-status-cash').fill('12000')
            page.locator('#sale-status-confirm-form').get_by_role('button', name='Подтвердить', exact=True).click()
            dialog = page.get_by_role('dialog').filter(has=page.get_by_role('heading', name='Подтвердите расчёт задолженности'))
            expect(dialog).to_be_visible()
            dialog.locator('textarea').fill('Погашение долга вместе с оплатой')
            dialog.get_by_role('button', name='Подтвердить расчёт', exact=True).click()
            expect(row).to_have_count(0)
            paid = run(lambda: Sale.objects.get(pk=sale.pk))
            self.assertEqual((paid.payment_status, paid.debt_repayment_amount, paid.extra_cash_amount), ('paid', 2000, 0))
            self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), 1000)
            self.assertEqual(run(lambda: Warehouse.objects.get(pk=warehouse.pk).cash_register.balance), 0)
            browser.close()

    def test_wholesale_offset_confirmation_and_contacts_permissions(self):
        actor = User.objects.create_superuser('partner-browser')
        warehouse = Warehouse.objects.create(name='Склад браузера')
        partner = Partner.objects.create(name='Магазин Игромир', contact_person='Иван', phone_1='00123')
        product = CD.objects.create(name='Игра', platform=Platform.objects.create(name='PS5'), cost=6000,
            wholesale_price=10000, avito_price=11000, barcode='000000123456')
        CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        adjust_creditor_debt(actor=actor, creditor_id=partner.creditor_id, warehouse_id=warehouse.pk,
            money_source_type='offset', new_debt='-3000', comment='Начальный долг')
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/partners_20261023/browser'
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
            page.goto(self.live_server_url + reverse('sales:create'))
            page.locator('#id_warehouse').select_option(str(warehouse.pk))
            expect(page.locator('#id_customer')).to_be_hidden()
            page.locator('#id_sale_type').select_option('wholesale')
            page.locator('#id_customer').select_option(str(partner.pk))
            page.locator('[data-sale-barcode-input]').fill('000000123456')
            page.locator('[data-sale-barcode-input]').press('Enter')
            expect(page.locator('[data-sale-intermediate-total]')).to_have_text('10 000,00 ₽')
            page.locator('#id_cash_received_amount').fill('8000')
            page.get_by_role('button', name='Продажа выполнена', exact=True).click()
            dialog = page.get_by_role('dialog').filter(has=page.get_by_role('heading', name='Подтвердите расчёт задолженности'))
            expect(dialog).to_be_visible()
            expect(dialog).to_contain_text('2 000,00')
            dialog.get_by_role('button', name='Отмена', exact=True).click()
            self.assertEqual(run(lambda: Sale.objects.count()), 0)
            page.get_by_role('button', name='Продажа выполнена', exact=True).click()
            expect(dialog).to_be_visible()
            dialog.locator('textarea').fill('Частичная оплата и взаимозачёт')
            dialog.screenshot(path=str(output / 'settlement.png'))
            dialog.get_by_role('button', name='Подтвердить расчёт', exact=True).click()
            page.wait_for_url(re.compile(r'/sales/\d+/$'))
            sale = run(lambda: Sale.objects.latest('pk'))
            self.assertEqual((sale.partner_id, sale.cash_received_amount, sale.debt_offset_amount), (partner.pk, 8000, 2000))
            self.assertEqual(run(lambda: Partner.objects.get(pk=partner.pk).creditor.current_debt), -1000)
            self.assertEqual(run(lambda: Warehouse.objects.get(pk=warehouse.pk).cash_register.balance), 8000)
            page.goto(self.live_server_url + reverse('partners:partner_detail', args=[partner.pk]))
            expect(page.get_by_role('heading', name=partner.name, exact=True)).to_be_visible()
            page.screenshot(path=str(output / 'partner.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 900})
            page.goto(self.live_server_url + reverse('sales:create'))
            page.locator('#id_sale_type').select_option('wholesale')
            page.screenshot(path=str(output / 'mobile.png'), full_page=True)
            self.assertEqual(errors, [])
            browser.close()
