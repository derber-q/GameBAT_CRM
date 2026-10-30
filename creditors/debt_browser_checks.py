"""Изменение долга в браузере с проверкой проводки в отдельной БД."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from partners.models import Partner
from sales.payment_browser_checks import database_call
from warehouse.models import Warehouse
from .services import adjust_creditor_debt


class DebtAdjustmentBrowserChecks(StaticLiveServerTestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('debt-browser')
        self.warehouse = Warehouse.objects.create(name='Склад долга')
        self.creditor = Partner.objects.create(name='GameShop', contact_person='Максим').creditor
        register = self.warehouse.cash_register
        register.balance = Decimal('200000')
        register.save(update_fields=['balance'])
        adjust_creditor_debt(actor=self.actor, creditor_id=self.creditor.pk,
            warehouse_id=self.warehouse.pk, money_source_type='offset', new_debt='121000', comment='Начальный долг')
        self.client.force_login(self.actor)
        self.output = Path(settings.BASE_DIR) / 'outputs/creditor-debt-20261027'
        self.output.mkdir(parents=True, exist_ok=True)

    def context(self, browser, **options):
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, **options)
        context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
            'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
        context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
        return context

    def test_modes_signed_preview_precision_mobile_and_cash_post(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = self.context(browser)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('creditors:debt', args=[self.creditor.pk]))
            page.locator('#id_warehouse').select_option(str(self.warehouse.pk))
            mode = page.locator('[name="amount_mode"][value="change"]')
            mode.check()
            amount = page.locator('#id_change_amount')
            preview = page.locator('[data-debt-preview]')
            amount.fill('500,25')
            expect(preview).to_have_text(re.compile(r'121\s500,25 ₽'))
            page.locator('[name="change_direction"][value="-"]').check()
            expect(preview).to_have_text(re.compile(r'120\s499,75 ₽'))
            page.locator('[name="amount_mode"][value="total"]').check()
            expect(page.locator('#id_new_debt')).to_have_value('120499,75')
            page.locator('#id_new_debt').fill('100000')
            expect(preview).to_have_text(re.compile(r'−21\s000,00 ₽'))
            mode.check()
            expect(amount).to_have_value('21000,00')
            expect(page.locator('[name="change_direction"][value="-"]')).to_be_checked()
            page.locator('[name="change_direction"][value="+"]').check()
            amount.fill('90071992547409,93')
            expect(preview).to_have_text(re.compile(r'90\s071\s992\s668\s409,93 ₽'))
            amount.fill('0,01')
            expect(preview).to_have_text(re.compile(r'121\s000,01 ₽'))
            amount.fill('500,25')
            page.locator('[name="change_direction"][value="-"]').check()
            for width in (1440, 390, 320):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width,
                    page.evaluate('''() => [...document.body.querySelectorAll('*')]
                        .filter(node => node.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
                        .slice(0, 12).map(node => ({tag: node.tagName, class: node.className, id: node.id,
                            width: node.getBoundingClientRect().width, right: node.getBoundingClientRect().right}))'''))
                expect(amount).to_be_visible()
                page.screenshot(path=str(self.output / f'debt-{width}.png'), full_page=True)
            page.get_by_role('button', name='Провести операцию', exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse('creditors:detail', args=[self.creditor.pk]))
            self.assertEqual(errors, [])
            browser.close()
        self.creditor.refresh_from_db()
        register = self.warehouse.cash_register
        register.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, register.balance), (Decimal('120499.75'), Decimal('200500.25')))
        operation = self.creditor.transactions.first()
        self.assertEqual((operation.old_debt, operation.new_debt, operation.delta),
            (Decimal('121000'), Decimal('120499.75'), Decimal('-500.25')))

    def test_validation_preserves_relative_input_and_uses_latest_balance(self):
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = self.context(browser).new_page()
            page.goto(self.live_server_url + reverse('creditors:debt', args=[self.creditor.pk]))
            page.locator('#id_warehouse').select_option(str(self.warehouse.pk))
            page.locator('[name="amount_mode"][value="change"]').check()
            page.locator('#id_change_amount').fill('300000')
            page.get_by_role('button', name='Провести операцию', exact=True).click()
            expect(page.locator('.alert-error')).to_contain_text('Недостаточно средств')
            expect(page.locator('[name="amount_mode"][value="change"]')).to_be_checked()
            expect(page.locator('#id_change_amount')).to_have_value('300000')
            database.submit(database_call, lambda: adjust_creditor_debt(actor=self.actor,
                creditor_id=self.creditor.pk, warehouse_id=self.warehouse.pk,
                money_source_type='offset', debt_delta='1000', comment='Другая операция')).result()
            page.locator('#id_change_amount').fill('100')
            page.get_by_role('button', name='Провести операцию', exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse('creditors:detail', args=[self.creditor.pk]))
            browser.close()
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('122100'))

    def test_relative_form_works_without_javascript(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = self.context(browser, java_script_enabled=False).new_page()
            page.goto(self.live_server_url + reverse('creditors:debt', args=[self.creditor.pk]))
            page.locator('#id_warehouse').select_option(str(self.warehouse.pk))
            page.locator('[name="amount_mode"][value="change"]').check()
            page.locator('[name="change_direction"][value="-"]').check()
            page.locator('#id_change_amount').fill('10,10')
            page.get_by_role('button', name='Провести операцию', exact=True).click()
            expect(page).to_have_url(self.live_server_url + reverse('creditors:detail', args=[self.creditor.pk]))
            browser.close()
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('120989.90'))
