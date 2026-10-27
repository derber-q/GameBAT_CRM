"""Реальное MV3-расширение в Chromium: Avito подменён локальным ответом, CRM настоящая тестовая."""
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
from catalog.models import CD, Platform
from integrations.models import AvitoProductProfile, AvitoRemoteListing, AvitoListingConnection, AvitoManualPrice
from sales.payment_browser_checks import database_call
from warehouse.models import Warehouse, CDWarehouseStock


AVITO_RESULTS = '''<!doctype html><html lang="ru"><meta charset="utf-8"><title>Avito — тестовая выдача</title>
<style>
body{font:16px Arial;margin:24px;background:#f5f7fa;color:#172735}.cards{display:flex;gap:16px;max-width:970px;flex-wrap:wrap}
article{width:280px;background:white;border:1px solid #dde4e9;border-radius:10px;padding:14px}a{color:#0078cf}
.photo{display:block;background:#e3ebf0;padding:45px 15px;text-align:center;border-radius:6px}.redesignDiscountWrapper-test{position:relative;color:#009bff;background:#e8f6ff;text-decoration:line-through}
.redesignDiscount-test{position:absolute;top:50%;left:0;right:0;height:2px;background:#009bff}[data-marker="old-price-value"]{color:#009bff}
</style><body><h1>Результаты поиска</h1><div class="cards">
<article data-marker="item" data-item-id="101" id="discount-card">
<a class="photo" href="/test/game_101" target="_blank">Фото товара</a><h2><a data-marker="item-title" href="/test/game_101" target="_blank">Игра со скидкой</a></h2>
<p data-marker="item-price"><meta itemprop="price" content="5789"><strong><span data-marker="item-price-value">5 789 ₽</span></strong></p>
<div class="redesignDiscountWrapper-test"><span data-marker="old-price-value">5&nbsp;890&nbsp;₽</span><div class="redesignDiscount-test"></div></div><span style="color:#009bff">−11 ₽ бонусами</span></article>
<article data-marker="item" data-item-id="102" id="plain-card"><a data-marker="item-title" href="/test/game_102" target="_blank">Игра без скидки</a>
<p data-marker="item-price"><meta itemprop="price" content="3990"><span data-marker="item-price-value">3 990 ₽</span></p></article>
<article data-marker="item" data-item-id="103" id="unknown-card"><a data-marker="item-title" href="/test/game_103" target="_blank">Неясная обычная цена</a>
<p data-marker="item-price"><meta itemprop="price" content="100"><span data-marker="item-price-value">100 ₽</span></p><span data-marker="old-price-value">Уточняйте</span></article>
<article data-marker="item" data-item-id="104" id="bonus-card"><a class="photo" href="/test/kena_104" target="_blank">Фото Kena</a>
<h2><a data-marker="item-title" href="/test/kena_104" target="_blank">Kena: Bridge of Spirits Deluxe Edition PS5</a></h2>
<div class="bonus-price-area" style="text-decoration:line-through;color:#009bff;background:#e8f6ff">
<p data-marker="item-price"><meta itemprop="price" content="1887"><span data-marker="item-price-value">1 887 ₽</span></p>
<div class="redesignDiscountWrapper-test"><span data-marker="old-price-value">1\u200e 890\u200b ₽<span> −3 ₽ бонусами</span></span><div class="redesignDiscount-test"></div></div>
</div></article>
<article data-marker="item" data-item-id="105" id="semantic-card"><h2><a data-marker="item-title" href="/test/kena_105" target="_blank">Kena без маркера старой цены</a></h2>
<div class="price-area"><p data-marker="item-price"><meta itemprop="price" content="1796"><span data-marker="item-price-value">1 796 ₽</span></p><s>1 799 ₽</s><span> −3 ₽ бонусами</span></div>
</article>
<article data-marker="item" data-item-id="106" id="markerless-bonus-card"><a data-marker="item-title" href="/test/kena_106">Kena: бонусная строка без маркеров</a>
<div class="price-area"><p data-marker="item-price"><meta itemprop="price" content="1548"><span data-marker="item-price-value">1 548 ₽</span></p><div class="bonus-wrapper"><span>1 550 ₽ −2 ₽ бонусами</span></div></div>
</article>
<article data-marker="item" id="unmarked-discount-card"><h2><a data-marker="item-title" href="/test/game_107">Цена без маркера скидочной суммы</a></h2>
<p data-marker="item-price"><meta itemprop="price" content="4392"><strong>4 392 ₽</strong></p>
<span data-marker="old-price-value">4 400 ₽</span></article>
</div></body></html>'''


class AvitoExtensionBrowserChecks(StaticLiveServerTestCase):
    def test_prefill_save_next_errors_conflict_empty_price_and_completion(self):
        actor = User.objects.create_superuser('extension-browser')
        platform = Platform.objects.create(name='PlayStation 5')
        warehouse = Warehouse.objects.create(name='Склад расширения')
        products = []
        for index, name in enumerate(('Alpha', 'Beta', 'Gamma'), start=1):
            product = CD.objects.create(name='PS5 ' + name, platform=platform, cost=500,
                wholesale_price=1200, avito_price=1500)
            CDWarehouseStock.objects.create(cd=product, warehouse=warehouse, quantity=1)
            profile = AvitoProductProfile.objects.create(cd=product)
            AvitoListingConnection.objects.create(profile=profile,
                remote_listing=AvitoRemoteListing.objects.create(avito_item_id=index))
            if index < 3:
                AvitoManualPrice.objects.create(profile=profile, price='1000.25' if index == 1 else '2000',
                    recorded_at=timezone.now(), recorded_by=actor)
            products.append(product)
        self.client.force_login(actor)
        folder = Path(settings.BASE_DIR) / 'outputs/avito_extension_20261023/browser'
        folder.mkdir(parents=True, exist_ok=True)
        extension = Path(settings.BASE_DIR) / 'browser_extensions/avito_check'
        with ThreadPoolExecutor(max_workers=1) as database, TemporaryDirectory(ignore_cleanup_errors=True) as profile_dir, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            context = pw.chromium.launch_persistent_context(profile_dir, channel='chromium', headless=True,
                viewport={'width':1440,'height':900}, args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}'])
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('https://www.avito.ru/**', lambda route: route.fulfill(content_type='text/html',
                body=AVITO_RESULTS))
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates':{},'available':False}))
            errors = []
            context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
            page = context.new_page()
            with patch('integrations.avito_check.ReefApiClient') as paid_api:
                page.goto(self.live_server_url + reverse('pricing:avito_check') + '?q=PS5&sort=name')
                expect(page.locator('html')).to_have_attribute('data-resource-avito-connected','1')
                expect(page.locator('[data-manual-extension-status]')).to_contain_text('Расширение подключено')
                with context.expect_page() as opened:
                    page.locator('[data-avito-manual-product]').first.click()
                avito = opened.value
                panel = avito.locator('resource-avito-check')
                expect(panel.locator('h2')).to_have_text('PS5 Alpha')
                field = panel.get_by_label('Минимальная цена, ₽')
                expect(field).to_have_value('1000.25')
                discount = avito.locator('#discount-card')
                old = discount.locator('[data-marker="old-price-value"]')
                current = discount.locator('[data-marker="item-price-value"]')
                expect(panel).to_have_attribute('data-version','1.4.0')
                expect(old).to_have_css('color','rgb(17, 17, 17)')
                expect(old).to_have_css('text-decoration-line','none')
                expect(discount.locator('.redesignDiscountWrapper-test')).to_have_css('text-decoration-line','none')
                expect(discount.locator('.redesignDiscount-test')).to_have_css('display','none')
                expect(current).not_to_be_visible()
                expect(discount.locator('[data-marker="item-price"]')).to_have_css('display','none')
                self.assertEqual(old.evaluate('e => getComputedStyle(e,"::after").fontSize'),'24px')
                expect(avito.locator('#plain-card [data-marker="item-price-value"]')).to_have_css('text-decoration-line','none')
                expect(avito.locator('#plain-card [data-marker="item-price-value"]')).to_have_css('font-size','24px')
                unmarked = avito.locator('#unmarked-discount-card')
                expect(unmarked.locator('[data-marker="item-price"]')).not_to_be_visible()
                expect(unmarked.locator('[data-marker="old-price-value"]')).to_be_visible()
                unmarked.click()
                expect(field).to_have_value('4400')
                field.fill('1000.25')
                bonus = avito.locator('#bonus-card')
                bonus_old = bonus.locator('[data-marker="old-price-value"]')
                expect(bonus_old).to_have_attribute('data-resource-price-text','1\u00a0890 ₽')
                expect(bonus.locator('.bonus-price-area')).to_have_css('text-decoration-line','none')
                self.assertEqual(bonus_old.evaluate('e => getComputedStyle(e,"::after").textDecorationLine'),'none')
                self.assertEqual(bonus_old.evaluate('e => getComputedStyle(e,"::after").color'),'rgb(17, 17, 17)')
                plain = avito.locator('#plain-card [data-marker="item-price-value"]')
                expect(old).to_have_attribute('data-resource-price-comparison','higher')
                field.fill('3400')
                expect(old).to_have_css('background-color','rgb(255, 135, 146)')
                expect(bonus_old).to_have_attribute('data-resource-price-comparison','lower')
                expect(bonus_old).to_have_css('background-color','rgb(104, 237, 131)')
                expect(plain).to_have_attribute('data-resource-price-comparison','higher')
                expect(current).not_to_have_attribute('data-resource-price-comparison')
                expect(avito.locator('#unknown-card [data-marker="old-price-value"]')).not_to_have_attribute('data-resource-price-comparison')
                # Сравнивается цена без скидки 5890, даже когда скидочная 5789 ниже минимума.
                field.fill('5800')
                expect(old).to_have_attribute('data-resource-price-comparison','higher')
                field.fill('1890,00')
                expect(bonus_old).to_have_attribute('data-resource-price-comparison','equal')
                expect(bonus_old).to_have_css('background-color','rgb(255, 227, 77)')
                for invalid in ('', 'ошибка', '0'):
                    field.fill(invalid)
                    expect(avito.locator('[data-resource-price-comparison]')).to_have_count(0)
                field.fill('3990')
                expect(plain).to_have_css('background-color','rgb(255, 227, 77)')
                avito.screenshot(path=str(folder/'price-comparison-140.png'))
                for target in (bonus.locator('.photo'),bonus.locator('[data-marker="item-title"]'),bonus_old):
                    target.click()
                    expect(field).to_have_value('1890')
                    expect(bonus_old).to_have_attribute('data-resource-price-comparison','equal')
                avito.locator('#semantic-card').click()
                expect(field).to_have_value('1799')
                markerless = avito.locator('#markerless-bonus-card')
                markerless.click()
                expect(field).to_have_value('1550')
                expect(markerless.locator('[data-resource-old-price]')).to_have_attribute('data-resource-price-text','1\u00a0550 ₽')
                bonus.click()
                avito.screenshot(path=str(folder/'kena-price-fixed.png'))
                initial_url, initial_pages = avito.url,len(context.pages)
                for target in (discount.locator('.photo'), discount.locator('[data-marker="item-title"]'), old):
                    target.click()
                    expect(field).to_have_value('5890')
                    self.assertEqual(avito.url,initial_url)
                    self.assertEqual(len(context.pages),initial_pages)
                discount.locator('[data-marker="item-title"]').click(modifiers=['Control'])
                discount.locator('[data-marker="item-title"]').click(button='middle')
                self.assertEqual(len(context.pages),initial_pages)
                expect(discount.locator('[data-marker="item-title"]')).not_to_have_attribute('href')
                avito.locator('#plain-card').click()
                expect(field).to_have_value('3990')
                discount.focus()
                discount.press('Enter')
                expect(field).to_have_value('5890')
                avito.locator('#unknown-card').click()
                expect(panel.get_by_role('alert')).to_contain_text('Не удалось однозначно определить цену без скидки')
                expect(field).to_have_value('5890')
                # Клик выбирает цену локально, не записывая её в CRM.
                self.assertEqual(run(lambda:AvitoManualPrice.objects.get(profile__cd=products[0]).price),Decimal('1000.25'))
                avito.evaluate('''() => {const card=document.querySelector('#discount-card').cloneNode(true);card.id='dynamic-card';card.querySelector('[data-marker="old-price-value"]').textContent='6 100,50 ₽';card.querySelector('[data-marker="item-title"]').setAttribute('href','/test/game_104');document.querySelector('.cards').append(card);}''')
                dynamic = avito.locator('#dynamic-card')
                expect(dynamic.locator('[data-marker="item-title"]')).not_to_have_attribute('href')
                expect(dynamic.locator('[data-marker="item-price-value"]')).not_to_be_visible()
                expect(dynamic.locator('[data-marker="old-price-value"]')).to_have_attribute('data-resource-price-comparison','higher')
                dynamic.click()
                expect(field).to_have_value('6100.50')
                avito.screenshot(path=str(folder/'card-price-selected.png'))
                avito.evaluate('''() => document.querySelector('#dynamic-card .redesignDiscountWrapper-test').remove()''')
                expect(dynamic.locator('[data-marker="item-price-value"]')).to_have_css('text-decoration-line','none')
                expect(dynamic.locator('[data-marker="item-price-value"]')).to_be_visible()
                expect(dynamic.locator('[data-marker="item-price-value"]')).to_have_attribute('data-resource-price-comparison','lower')
                dynamic.focus()
                dynamic.press('Space')
                expect(field).to_have_value('5789')
                field.fill('999,50')
                fail = lambda route: route.fulfill(status=503,json={'ok':False,'message':'Тестовая ошибка CRM'})
                context.route('**/avito-check/found-price/', fail)
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.get_by_role('alert')).to_have_text('Тестовая ошибка CRM')
                expect(panel.locator('h2')).to_have_text('PS5 Alpha')
                self.assertEqual(run(lambda:AvitoManualPrice.objects.get(profile__cd=products[0]).price),Decimal('1000.25'))
                context.unroute('**/avito-check/found-price/', fail)
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.locator('h2')).to_have_text('PS5 Beta')
                expect(field).to_have_value('2000.00')
                expect(bonus_old).to_have_attribute('data-resource-price-comparison','lower')
                expect(page.locator('[data-found-price-form] [name="price"]').first).to_have_value('999.50')
                avito.reload()
                expect(panel.locator('h2')).to_have_text('PS5 Beta')
                def change_elsewhere():
                    found=AvitoManualPrice.objects.get(profile__cd=products[1])
                    found.price,found.recorded_at=Decimal('2222'),timezone.now()
                    found.save(update_fields=('price','recorded_at'))
                run(change_elsewhere)
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.get_by_role('alert')).to_contain_text('Минимальная цена уже изменена')
                expect(panel.locator('h2')).to_have_text('PS5 Beta')
                panel.get_by_role('button',name='Обновить панель').click()
                expect(field).to_have_value('2222.00')
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel.locator('h2')).to_have_text('PS5 Gamma')
                expect(field).to_have_value('')
                expect(avito.locator('[data-resource-price-comparison]')).to_have_count(0)
                avito.set_viewport_size({'width':390,'height':850})
                avito.screenshot(path=str(folder/'mobile.png'))
                field.fill('1500')
                panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(panel).to_have_attribute('data-state','done')
                expect(avito.locator('[data-resource-price-comparison]')).to_have_count(0)
                expect(panel.locator('h2')).to_have_text('Проверка списка завершена')
                self.assertEqual(run(lambda:list(AvitoManualPrice.objects.order_by('profile__cd_id').values_list('price',flat=True))),
                    [Decimal('999.50'),Decimal('2222'),Decimal('1500')])
                self.assertEqual(run(lambda:list(CD.objects.order_by('pk').values_list('avito_price',flat=True))),[Decimal('1500')]*3)
                # Закрытая исходная вкладка не позволяет записать цену через чужую сессию.
                with context.expect_page() as reopened:
                    page.locator('[data-avito-manual-product]').first.click()
                last = reopened.value
                last_panel = last.locator('resource-avito-check')
                expect(last_panel.get_by_label('Минимальная цена, ₽')).to_have_value('999.50')
                page.close()
                last_panel.get_by_role('button',name='Сохранить и следующий').click()
                expect(last_panel.get_by_role('alert')).to_contain_text('Оставьте исходную вкладку')
                paid_api.assert_not_called()
            self.assertEqual(errors,[])
            context.close()

    def test_page_explains_missing_extension_without_breaking_regular_search(self):
        actor = User.objects.create_superuser('extension-status-browser')
        self.client.force_login(actor)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page = context.new_page()
            page.goto(self.live_server_url + reverse('pricing:avito_check'))
            expect(page.locator('[data-manual-extension-status]')).to_contain_text('Панель Avito не подключена')
            expect(page.locator('[data-manual-extension-status]')).to_contain_text('обновите эту страницу')
            browser.close()
