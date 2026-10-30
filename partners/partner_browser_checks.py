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
    def test_creditor_groups_colors_and_larger_outstanding_amounts(self):
        actor = User.objects.create_superuser('creditor-colors-browser')
        self.client.force_login(actor)
        ids = {}
        for name, amount in [('А Нулевой', '0'), ('Б Получатель', '-1500.25'), ('Я Должник', '2000.50')]:
            partner = Partner.objects.create(name=name, contact_person='Иван')
            creditor = partner.creditor
            creditor.current_debt = amount
            creditor.save(update_fields=['current_debt'])
            ids[name] = creditor.pk
        output = Path(settings.BASE_DIR) / 'outputs/creditor-debt-layout-20261027'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 950})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            page.goto(self.live_server_url + reverse('creditors:list'))
            self.assertEqual(page.locator('[data-creditor-id]').evaluate_all('rows => rows.map(row => Number(row.dataset.creditorId))'),
                [ids['Я Должник'], ids['Б Получатель'], ids['А Нулевой']])
            for name, color in [('Я Должник', 'rgb(254, 226, 226)'), ('Б Получатель', 'rgb(220, 252, 231)'), ('А Нулевой', 'rgb(255, 255, 255)')]:
                row = page.locator(f'[data-creditor-id="{ids[name]}"]')
                expect(row.locator('td').first).to_have_css('background-color', color)
                row.hover()
                expect(row.locator('td').last).to_have_css('background-color', color)
                title = row.locator('.creditor-name')
                expect(title).to_have_css('font-size', '20px')
                expect(title).to_have_css('color', 'rgb(0, 0, 0)')
                title.hover()
                expect(title).to_have_css('color', 'rgb(0, 0, 0)')
                amount = row.locator('.creditor-debt-amount')
                if name == 'А Нулевой':
                    expect(amount).not_to_have_css('font-size', '22px')
                else:
                    expect(amount).to_have_css('font-size', '22px')
                    expect(amount).to_have_css('font-weight', '800')
            expect(page.get_by_role('link', name='Редактировать', exact=True)).to_have_count(0)
            expect(page.get_by_role('link', name='Изменить долг', exact=True)).to_have_count(3)
            page.screenshot(path=str(output / 'creditors.png'), full_page=True)
            menu = page.locator('[data-counterparties-nav]')
            trigger = menu.locator('.nav-dropdown-trigger')
            expect(trigger).to_have_attribute('href', reverse('partners:partner_list'))
            expect(page.locator('.main-nav > a').filter(has_text=re.compile('^(Партнёры|Кредиторы|Поставщики)$'))).to_have_count(0)
            trigger.hover()
            for label in ('Партнёры', 'Кредиторы', 'Поставщики'):
                expect(menu.get_by_role('link', name=label, exact=True)).to_be_visible()
            page.screenshot(path=str(output / 'counterparties-menu.png'), full_page=True)
            trigger.click()
            expect(page).to_have_url(self.live_server_url + reverse('partners:partner_list'))
            for endpoint, label in [('partners:list', 'Поставщики'), ('creditors:list', 'Кредиторы')]:
                menu.locator('.nav-dropdown-trigger').focus()
                expect(menu.get_by_role('link', name=label, exact=True)).to_be_visible()
                menu.get_by_role('link', name=label, exact=True).click()
                expect(page).to_have_url(self.live_server_url + reverse(endpoint))
                expect(menu.locator('.nav-dropdown-trigger')).to_have_class(re.compile(r'\bactive\b'))
                expect(page.locator('.main-nav .nav-dropdown-trigger').filter(has_text='stuf')).not_to_have_class(re.compile(r'\bactive\b'))
            warehouse_menu = page.locator('[data-warehouse-nav]')
            warehouse_menu.locator('.nav-dropdown-trigger').hover()
            expect(warehouse_menu.locator('.nav-dropdown-menu a').first).to_have_text('Приход')
            expect(page.locator('.main-nav > a').filter(has_text=re.compile('^Приход$'))).to_have_count(0)
            page.screenshot(path=str(output / 'warehouse-supplies-menu.png'), full_page=True)
            warehouse_menu.get_by_role('link', name='Приход', exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse('supplies:list'))
            expect(warehouse_menu.locator('.nav-dropdown-trigger')).to_have_class(re.compile(r'\bactive\b'))
            browser.close()

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
            expect(page.locator(f'#id_customer option[value="{partner.pk}"]')).to_have_text('Магазин Игромир (Иван)')
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
            page.goto(self.live_server_url + reverse('creditors:list'))
            expect(page.get_by_role('link', name='Магазин Игромир (Иван)', exact=True)).to_be_visible()
            page.screenshot(path=str(output / 'creditor-contact-name.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 900})
            page.goto(self.live_server_url + reverse('sales:create'))
            page.locator('#id_sale_type').select_option('wholesale')
            page.screenshot(path=str(output / 'mobile.png'), full_page=True)
            self.assertEqual(errors, [])
            browser.close()
