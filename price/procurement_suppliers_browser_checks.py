"""Выбор поставщика и сохранение в Chromium, без рабочего API и рабочей БД."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright
from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice
from sales.payment_browser_checks import database_call
from .services import create_procurement_price_list


class ProcurementSupplierBrowserChecks(StaticLiveServerTestCase):
    def test_supplier_choice_recalculates_cd_and_tech_persists_and_fits_phone(self):
        actor = User.objects.create_superuser('procurement-supplier-browser')
        self.client.force_login(actor)
        cd = CD.objects.create(name='Игра для закупки', platform=Platform.objects.create(name='PS5'), sku='B-CD')
        tech = Tech.objects.create(name='Контроллер для закупки', brand=Brand.objects.create(name='Sony'),
            product_type=ProductType.objects.create(name='Контроллер'), weight_grams=1000, sku='B-TECH')
        suppliers = {}
        for letter, amount in [('A', 10), ('F', 15), ('M', 9)]:
            supplier = Supplier.objects.create(name=letter, letter=letter, highlight_color='#37A7BA', legal_entity=letter, phone_1='1')
            suppliers[letter] = supplier
            SupplierCDPrice.objects.create(supplier=supplier, cd=cd, price=amount)
            SupplierTechPrice.objects.create(supplier=supplier, tech=tech, price=amount * 10)
        price = create_procurement_price_list(actor=actor, exchange_rate_usdt_aed='3.67', exchange_rate_usdt_rub=90,
            delivery_general_usdt_per_kg=2, delivery_devices_usdt_per_kg=2, delivery_storage_usdt_per_kg=2,
            delivery_cd_rub=5, postpayment_surcharges={tech.pk: 125})
        cd_id, tech_id = price.items.get(cd=cd).pk, price.items.get(tech=tech).pk
        output = Path(settings.BASE_DIR) / 'outputs/procurement-suppliers-20261027/browser'
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 950})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('price:procurement_detail', args=[price.pk]))
            cd_row = page.locator(f'[data-item-id="{cd_id}"]')
            tech_row = page.locator(f'[data-item-id="{tech_id}"]')
            self.assertEqual(page.locator('[data-procurement-row]').evaluate_all(
                'rows => rows.map(row => Number(row.dataset.itemId))'), [tech_id, cd_id])
            expect(page.get_by_role('columnheader', name='Цены поставщиков, AED', exact=True)).to_be_visible()
            expect(page.get_by_role('columnheader', name='Курс', exact=True)).to_have_count(0)
            expect(page.get_by_role('columnheader', name='Итоговая себестоимость, RUB', exact=True)).to_have_count(1)
            expect(page.locator('[data-prepayment-rounding], [data-postpayment-rounding]')).to_have_count(0)
            expect(cd_row.locator('[data-total-cost-display]')).to_have_text('225.71')
            for letter, amount in [('A', 10), ('F', 15), ('M', 9)]:
                expect(cd_row.locator(f'[data-supplier-id="{suppliers[letter].pk}"]')).to_have_text(f'{letter}–{amount}')
            expensive_cd = cd_row.locator(f'[data-supplier-id="{suppliers["F"].pk}"]')
            expect(expensive_cd).to_have_css('color', 'rgb(185, 28, 28)')
            expect(cd_row.locator('.is-expensive')).to_have_count(1)
            expect(tech_row.locator('.is-expensive')).to_have_count(0)
            cd_row.locator('[data-supplier-select]').select_option(str(suppliers['A'].pk))
            expect(cd_row.locator('.is-expensive')).to_have_count(1)
            expect(expensive_cd).to_have_css('color', 'rgb(185, 28, 28)')
            cd_row.locator('[data-supplier-select]').select_option(str(suppliers['M'].pk))
            expect(expensive_cd).to_have_css('color', 'rgb(185, 28, 28)')
            page.screenshot(path=str(output / 'cd-expensive-offer.png'), full_page=True)
            cd_row.locator('[data-markup]').fill('123.45')
            cd_row.locator('[data-supplier-select]').select_option(str(suppliers['F'].pk))
            expect(cd_row.locator('[data-total-cost-display]')).to_have_text('372.85')
            expect(cd_row.locator('[data-prepayment]')).to_have_value('500.00')
            expect(cd_row.locator('[data-postpayment]')).to_have_value('560.00')
            expect(cd_row.locator('.is-selected')).to_have_text('F–15')
            expect(cd_row.locator('.is-expensive')).to_have_count(0)
            expect(cd_row.locator('.is-selected')).to_have_css('background-color', 'rgb(220, 252, 231)')
            cd_row.locator('[data-delivery]').fill('15.25')
            expect(cd_row.locator('[data-total-cost-display]')).to_have_text('383.10')
            expect(cd_row.locator('[data-prepayment]')).to_have_value('510.00')
            expect(cd_row.locator('[data-postpayment]')).to_have_value('570.00')
            tech_row.locator('[data-markup]').fill('50.01')
            tech_row.locator('[data-supplier-select]').select_option(str(suppliers['A'].pk))
            expect(tech_row.locator('[data-total-cost-display]')).to_have_text('2632.32')
            expect(tech_row.locator('[data-prepayment]')).to_have_value('2690.00')
            expect(tech_row.locator('[data-postpayment]')).to_have_value('2810.00')
            tech_row.locator('[data-delivery]').fill('200.12')
            expect(tech_row.locator('[data-total-cost-display]')).to_have_text('2652.44')
            page.screenshot(path=str(output / 'desktop.png'), full_page=True)
            for _ in range(2):
                page.get_by_role('button', name='Сохранить расчёт', exact=True).click()
                expect(cd_row.locator('[data-supplier-select]')).to_have_value(str(suppliers['F'].pk))
                expect(cd_row.locator('.is-selected')).to_have_text('F–15')
                expect(cd_row.locator('.is-expensive')).to_have_count(0)
                expect(cd_row.locator('[data-markup]')).to_have_value('123.45')
                expect(cd_row.locator('[data-total-cost-display]')).to_have_text('383.10')
                expect(cd_row.locator('[data-delivery]')).to_have_value('15.25')
                expect(tech_row.locator('[data-total-cost-display]')).to_have_text('2652.44')
                expect(tech_row.locator('[data-supplier-select]')).to_have_value(str(suppliers['A'].pk))
                saved = run(lambda: list(price.items.order_by('pk').values_list('selected_supplier__letter', flat=True)))
                self.assertEqual(saved, ['F', 'A'])
            page.set_viewport_size({'width': 390, 'height': 900})
            cd_row.locator('[data-supplier-select]').scroll_into_view_if_needed()
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            page.screenshot(path=str(output / 'phone.png'), full_page=True)
            self.assertEqual(errors, [])
            browser.close()
