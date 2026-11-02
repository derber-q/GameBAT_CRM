"""MV3 Chromium с подменённым Avito: форма, связь продажи и очередь этикетки."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import re
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright, expect
from PIL import Image
from accounts.models import User
from warehouse.models import Warehouse, CDWarehouseStock
from catalog.models import CD, Platform
from integrations.models import AvitoProductProfile, AvitoRemoteListing, AvitoListingConnection
from sales.models import AvitoBrowserOrder, AvitoShippingPrintJob, PrintAgent, Sale
from sales.payment_browser_checks import database_call


# Структура data-marker/ссылок взята из присланного outerHTML; данные искусственные.
LIST = '''<html lang="ru"><meta charset="utf-8"><style>
body{font:14px Arial;margin:24px;max-width:1000px}p,h5{margin:0 0 6px}h5{font-size:16px}
[data-marker="order-row"]{position:relative;margin-bottom:32px;padding:12px;box-sizing:border-box}
[data-marker="order-row"]>a{position:absolute;inset:0;z-index:1}
.order-main{display:flex;gap:24px}.order-info{flex:1;min-width:120px}.price{width:164px;flex:none}
.orderImages{width:300px;flex:none}[data-marker="images-row"]{height:56px}
[data-marker="images-row"] img{height:56px;width:75px;object-fit:contain;background:#e1e8ef;border-radius:8px}
@media(max-width:800px){.order-main{gap:12px}.orderImages{width:160px}.price{width:110px}}
</style><body><h1>Заказы и заявки</h1><div data-marker="order-row"><div class="order-main">
<div class="order-info"><h5 data-marker="order-status">Отправьте заказ</h5><p>До 5 ноября включительно</p></div><div class="price"><p>100 ₽</p><p>Почта России</p></div>
<div class="orderImages"><div style="width:240px;height:56px"><div data-marker="images-row"><img alt="Synthetic listing" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='112'%3E%3Crect width='150' height='112' fill='%23237e90'/%3E%3Ctext x='20' y='65' fill='white' font-size='24'%3ETest game%3C/text%3E%3C/svg%3E"></div></div></div></div>
<a href="/orders/70000000000000001?source=orders_list">Подробнее</a></div></body></html>'''
DETAIL = '''<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body><strong>Отправьте заказ через пункт Почты России</strong>
<p>Назовите этот номер или покажите штрихкод</p>
<script>
// Один заголовок запроса не превращает desktop JS/viewport в мобильную страницу.
if (/Android/.test(navigator.userAgent) && navigator.userAgentData?.mobile === true &&
    screen.width <= 430 && innerWidth <= 430 && navigator.maxTouchPoints > 0) {
  const code=document.createElement('img');
  code.src='https://avito.ru/web/1/barcode/generate?barcodeType=128&content=00123456789012&height=335&width=840';
  document.body.append(code);
}
</script></body></html>'''

# Искусственный QR P000000000001: фиксированная матрица, без новых зависимостей.
QR_MATRIX = '''111111101111101111111
100000100101001000001
101110100110001011101
101110100111001011101
101110100010101011101
100000100001101000001
111111101010101111111
000000001111100000000
110110100110101000001
110011001000101010111
010101100000001101111
011111000111000011101
010000100100011111101
000000001101111000111
111111100100110110101
100000100011100010100
101110101101101101111
101110101101100011100
101110100110011111111
100000101100011000110
111111101011010110110'''.splitlines()


@override_settings(LABEL_PRINT_BACKEND='agent')
class AvitoOrdersBrowserChecks(StaticLiveServerTestCase):
    def test_5post_svg_qr_uses_rendered_image_and_never_repeats_background_download(self):
        import pymupdf
        owner=User.objects.create_superuser('5post-browser')
        PrintAgent.objects.create(name='Test QR',printer_name='Fake',token_hash=hashlib.sha256(b'qr-test').hexdigest())
        self.client.force_login(owner)
        media=self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=media))
        detail=[DETAIL.replace('Почты России','5Post').replace('barcodeType=128','barcodeType=QR_IMAGE').replace('00123456789012','P000000000001')]
        rectangles=''.join(f'<rect x="{(x+4)*8}" y="{(y+4)*8}" width="8" height="8"/>'
            for y,line in enumerate(QR_MATRIX) for x,value in enumerate(line) if value=='1')
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="232" height="232"><rect width="232" height="232" fill="white"/><g fill="black">{rectangles}</g></svg>'
        load_image=[False]
        background_downloads=[]
        extension=Path(settings.BASE_DIR)/'browser_extensions/avito_check'
        with ThreadPoolExecutor(max_workers=1) as pool, TemporaryDirectory(ignore_cleanup_errors=True) as folder, sync_playwright() as pw:
            run=lambda f:pool.submit(database_call,f).result()
            context=pw.chromium.launch_persistent_context(folder,channel='chromium',headless=True,
                viewport={'width':1440,'height':900},args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}'])
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.live_server_url+'/') else route.abort())
            context.route('https://www.avito.ru/**',lambda route:route.fulfill(content_type='text/html',body=LIST.replace('Почта России','5Post')))
            context.route('https://m.avito.ru/**',lambda route:route.fulfill(content_type='text/html',body=detail[0]))
            def original_image(route):
                if route.request.resource_type!='image':
                    background_downloads.append(route.request.resource_type);route.abort()
                elif load_image[0]:route.fulfill(content_type='image/svg+xml',body=svg)
                else:route.abort()
            context.route('https://avito.ru/web/1/barcode/generate?*',original_image)
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            crm=context.new_page();crm.goto(self.live_server_url+'/crm/sales/avito-extension/')
            page=context.new_page();page.goto('https://www.avito.ru/orders')
            panel=page.locator('resource-avito-order')
            button=panel.get_by_text('Напечатать отправительный код',exact=True)
            button.click()
            expect(panel.locator('small')).to_contain_text('Avito не загрузил изображение',timeout=40000)
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.count()),0)
            load_image[0]=True
            button.click()
            expect(panel.locator('small')).to_contain_text('очередь',timeout=40000)
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.count()),1)
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.get().state),'agent_waiting')
            self.assertEqual(run(lambda:AvitoBrowserOrder.objects.get().carrier),'5Post')
            self.assertEqual(run(lambda:Sale.objects.count()),0)
            self.assertEqual(background_downloads,[])
            def read_pdf():
                with AvitoShippingPrintJob.objects.get().file.open('rb') as source:
                    return source.read()
            pdf=run(read_pdf)
            with pymupdf.open(stream=pdf,filetype='pdf') as document:
                self.assertAlmostEqual(document[0].rect.width*25.4/72,58,places=2)
                self.assertAlmostEqual(document[0].rect.height*25.4/72,40,places=2)
                self.assertIn('5Post',document[0].get_text())
                box=pymupdf.Rect(document[0].get_image_info()[0]['bbox'])
                self.assertAlmostEqual(box.width,box.height,places=2)
                image=document.extract_image(document[0].get_images()[0][0])
                bitmap=Image.open(BytesIO(image['image'])).convert('L')
                # Сравниваем каждую ячейку с оригинальным QR, включая порядок модулей.
                self.assertEqual(bitmap.width,bitmap.height)
                for y,line in enumerate(QR_MATRIX):
                    for x,value in enumerate(line):
                        pixel=bitmap.getpixel((int((x+4.5)*bitmap.width/29),int((y+4.5)*bitmap.height/29)))
                        self.assertEqual(pixel<128,value=='1')
            target=Path(settings.BASE_DIR)/'outputs/avito_orders_20261101'
            target.mkdir(exist_ok=True)
            (target/'sample_5post_label.pdf').write_bytes(pdf)
            self.assertFalse(any(p.url.startswith('https://m.avito.ru/orders/') for p in context.pages))
            # Распознанный QR не требует картинки: она намеренно недоступна,
            # но точные исходные данные с ведущими нулями доходят до генератора CRM.
            direct_id='70000000000000002'
            detail[0]=DETAIL.replace('Почты России','5Post').replace('barcodeType=128','barcodeType=QrCode').replace('00123456789012','001234567')
            load_image[0]=False
            context.route('https://www.avito.ru/**',lambda route:route.fulfill(content_type='text/html',body=LIST.replace('Почта России','5Post').replace('70000000000000001',direct_id)))
            received=[]
            def record_original_payload(route):
                if route.request.method=='POST' and route.request.post_data_json.get('action')=='print':
                    received.append(route.request.post_data_json.get('symbol'))
                route.fallback()
            context.route('**/crm/sales/avito-extension/',record_original_payload)
            page.reload()
            button.click()
            expect(panel.locator('small')).to_contain_text('очередь',timeout=40000)
            self.assertEqual(received,[{'type':'QR','content':'001234567'}])
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.count()),2)
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.get(order__external_id=direct_id).state),'agent_waiting')
            self.assertEqual(run(lambda:Sale.objects.count()),0)
            self.assertEqual(background_downloads,[])
            context.close()

    def test_buttons_open_form_keep_sale_link_and_enqueue_original_label(self):
        owner=User.objects.create_superuser('avito-browser')
        wh=Warehouse.objects.create(name='Synthetic warehouse')
        game=CD.objects.create(name='Synthetic game',platform=Platform.objects.create(name='Test'),avito_price=100)
        CDWarehouseStock.objects.create(warehouse=wh,cd=game,quantity=3)
        profile=AvitoProductProfile.objects.create(cd=game)
        listing=AvitoRemoteListing.objects.create(avito_item_id=123,title='Synthetic listing')
        AvitoListingConnection.objects.create(profile=profile,remote_listing=listing)
        PrintAgent.objects.create(name='Test',printer_name='Fake',token_hash=hashlib.sha256(b'synthetic').hexdigest())
        self.client.force_login(owner)
        png=BytesIO();Image.new('RGB',(840,335),'white').save(png,'PNG')
        extension=Path(settings.BASE_DIR)/'browser_extensions/avito_check'
        with ThreadPoolExecutor(max_workers=1) as pool, TemporaryDirectory(ignore_cleanup_errors=True) as folder, sync_playwright() as pw:
            run=lambda f:pool.submit(database_call,f).result()
            context=pw.chromium.launch_persistent_context(folder,channel='chromium',headless=True,
                viewport={'width':1440,'height':900},args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}'])
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.live_server_url+'/') else route.abort())
            context.route('https://www.avito.ru/**',lambda route:route.fulfill(content_type='text/html',body=LIST))
            context.route('https://m.avito.ru/**',lambda route:route.fulfill(content_type='text/html',body=DETAIL))
            context.route('https://avito.ru/web/1/barcode/generate?*',lambda route:route.fulfill(content_type='image/png',body=png.getvalue()))
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            crm=context.new_page();crm.goto(self.live_server_url+'/crm/sales/avito-extension/')
            page=context.new_page();page.goto('https://www.avito.ru/orders')
            panel=page.locator('[data-marker="order-row"]:has(>a[href*="70000000000000001"]) resource-avito-order')
            expect(panel.get_by_text('Создать продажу',exact=True)).to_be_visible()
            row=page.locator('[data-marker="order-row"]').first
            expect(row).to_have_attribute('data-resource-order-state','unlinked')
            expect(row).to_have_css('background-color','rgb(255, 241, 222)')
            product=row.locator('resource-avito-products')
            expect(product.get_by_text('Synthetic listing',exact=True)).to_be_visible()
            expect(product.locator('img')).to_be_visible()
            self.assertGreater(product.locator('img').bounding_box()['height'],56)
            # Сравниваем с прежней строкой, оставляя все кнопки/статусы CRM на месте.
            heights=row.evaluate('''row=>{
              const gallery=row.querySelector('resource-avito-products');
              const enhanced=row.getBoundingClientRect().height;
              gallery.style.display='none';row.classList.remove('resource-avito-order-row');
              const previous=row.getBoundingClientRect().height;
              gallery.style.display='';row.classList.add('resource-avito-order-row');
              return {enhanced,previous};
            }''')
            self.assertAlmostEqual(heights['enhanced'],heights['previous'],delta=1)
            with context.expect_page() as opened:panel.get_by_text('Создать продажу',exact=True).click()
            form=opened.value
            form.wait_for_url('**/crm/sales/avito-orders/*/create/')
            expect(form.locator('.stock-lines tr')).to_have_count(1)
            self.assertEqual(run(lambda:Sale.objects.count()),0)
            form.locator('#id_warehouse').select_option(str(wh.pk))
            expect(form.locator('[data-sale-intermediate-total]')).to_contain_text('100,00')
            form.locator('.stock-lines-form .submit-bar button[type="submit"]').click()
            try:
                form.wait_for_url(re.compile(r'/crm/sales/\d+/$'),timeout=8000)
            except Exception:
                print('FORM DIAGNOSTIC',form.locator('body').inner_text()[-8000:])
                print('FIELDS',form.locator('.stock-lines-form').evaluate('(f)=>Array.from(new FormData(f).entries()).filter(([k])=>k!=="csrfmiddlewaretoken")'))
                raise
            self.assertEqual(run(lambda:Sale.objects.count()),1)
            page.reload()
            expect(panel.get_by_role('link')).to_contain_text('SALE-')
            expect(row).to_have_attribute('data-resource-order-state','ready')
            expect(row).to_have_css('background-color','rgb(255, 255, 255)')
            for label,state,color in [('Едет к покупателю','transit','rgb(237, 248, 238)'),
                    ('Ждёт выдачи покупателю','transit','rgb(237, 248, 238)'),
                    ('Ждет выдачи покупателю','transit','rgb(237, 248, 238)'),
                    ('Получите оплату','payment','rgb(234, 243, 255)'),
                    ('Отправьте заказ','ready','rgb(255, 255, 255)')]:
                row.locator('[data-marker="order-status"]').evaluate('(el,text)=>el.textContent=text',label)
                expect(row).to_have_attribute('data-resource-order-state',state)
                expect(row).to_have_css('background-color',color)
            # Несколько фото/названий и изменение ширины не увеличивают высоту строки.
            original_image=row.locator('[data-marker="images-row"] img').first
            original_image.evaluate('''image=>{
              // Avito создаёт отдельный images-row для каждого товара заказа.
              const second=image.parentElement.cloneNode(true);
              second.querySelector('img').alt='Второй тестовый товар с длинным названием';
              image.parentElement.parentElement.append(second);
            }''')
            expect(product.locator('img')).to_have_count(2)
            expect(product.get_by_text('Второй тестовый товар с длинным названием',exact=True)).to_be_visible()
            page.bring_to_front()
            for width in [960,1440]:
                page.set_viewport_size({'width':width,'height':900})
                page.wait_for_function('''()=>{
                  const row=document.querySelector('[data-marker="order-row"]');
                  const gallery=row.querySelector('resource-avito-products');
                  return gallery.getBoundingClientRect().right<=row.getBoundingClientRect().right+1;
                }''')
                metrics=row.evaluate('''row=>{
                  const gallery=row.querySelector('resource-avito-products');
                  const bounds=row.getBoundingClientRect(),photo=gallery.getBoundingClientRect();
                  const cards=Array.from(gallery.shadowRoot.querySelectorAll('a')).map(el=>{
                    const r=el.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top};
                  });
                  gallery.style.display='none';const previous=row.getBoundingClientRect().height;gallery.style.display='';
                  return {height:bounds.height,previous,left:photo.left,right:photo.right,rowLeft:bounds.left,rowRight:bounds.right,cards};
                }''')
                self.assertAlmostEqual(metrics['height'],metrics['previous'],delta=1)
                self.assertGreaterEqual(metrics['left'],metrics['rowLeft'])
                self.assertLessEqual(metrics['right'],metrics['rowRight']+1)
                first,second=metrics['cards']
                self.assertAlmostEqual(first['top'],second['top'],delta=1)
                self.assertLessEqual(first['right'],second['left'])
                self.assertLessEqual(second['right'],metrics['right']+1)
                expect(row.locator('[data-marker="images-row"]')).to_have_count(2)
                for group in row.locator('[data-marker="images-row"]').all():
                    expect(group).to_have_css('visibility','hidden')
            target=Path(settings.BASE_DIR)/'outputs/avito_orders_20261102'
            target.mkdir(exist_ok=True)
            row.screenshot(path=str(target/'multiple_products.png'))
            original_image.evaluate("image=>image.alt='Обновлённое название тестового товара'")
            expect(product.get_by_text('Обновлённое название тестового товара',exact=True)).to_be_visible()
            original_image.evaluate("image=>{image.alt='Synthetic listing';image.parentElement.nextElementSibling.remove()}")
            expect(product.locator('img')).to_have_count(1)
            # Временный обрыв lookup не стирает связь; после восстановления ошибка исчезает.
            disconnected=[True]
            def connection_failure(route):
                if route.request.method=='POST' and route.request.post_data_json.get('action')=='lookup' and disconnected[0]:
                    route.fulfill(json={'ok':False,'message':'Тест: связь временно потеряна'})
                else:
                    route.fallback()
            context.route('**/crm/sales/avito-extension/',connection_failure)
            page.reload()
            expect(panel.locator('small')).to_contain_text('связь временно потеряна')
            disconnected[0]=False
            page.evaluate("document.body.append(document.createElement('i'))")
            expect(panel.get_by_role('link')).to_contain_text('SALE-')
            expect(panel.locator('small')).to_have_text('')
            self.assertEqual(run(lambda:Sale.objects.count()),1)
            panel.get_by_text('Напечатать отправительный код',exact=True).click()
            expect(panel.locator('small')).to_contain_text('очередь',timeout=40000)
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.count()),1)
            self.assertEqual(run(lambda:AvitoShippingPrintJob.objects.get().state),'agent_waiting')
            self.assertFalse(run(lambda:AvitoBrowserOrder.objects.get().sale.is_completed))
            self.assertFalse(any(p.url.startswith('https://m.avito.ru/orders/') for p in context.pages))
            self.assertFalse(page.evaluate("/Android/.test(navigator.userAgent)"))
            self.assertEqual(page.evaluate('innerWidth'),1440)
            # Самовывоз и обычная доставка не имеют отправительного кода.
            for index,method in enumerate(['Самовывоз','Доставка','Доставка продавцом','Достависта','Dostavista','Яндекс Доставка','СДЭК']):
                page.evaluate('''({id,method})=>{
                  const row=document.createElement('div');row.dataset.marker='order-row';
                  row.innerHTML='<h5 data-marker="order-status">Отправьте заказ</h5><p>100 ₽</p><p></p><a>Заказ</a>';
                  row.querySelectorAll('p')[1].textContent=method;
                  row.querySelector('a').setAttribute('href','/orders/'+id);
                  row.setAttribute('data-test-order',id);document.body.append(row);
                }''',{'id':str(index+100),'method':method})
                actions=page.locator(f'[data-test-order="{index+100}"] resource-avito-order')
                expect(actions.get_by_text('Создать продажу',exact=True)).to_be_visible()
                expect(actions.get_by_text('Напечатать отправительный код',exact=True)).to_have_count(0 if index<5 else 1)
            # Приоритет фона: отмена выше отсутствия продажи, отсутствие продажи выше оплаты.
            unlinked=page.locator('[data-test-order="100"]')
            unlinked.locator('[data-marker="order-status"]').evaluate("el=>el.textContent='Получите оплату'")
            expect(unlinked).to_have_attribute('data-resource-order-state','unlinked')
            unlinked.locator('[data-marker="order-status"]').evaluate("el=>el.textContent='Отменён'")
            expect(unlinked).to_have_attribute('data-resource-order-state','cancelled')
            # При смене способа в существующей строке кнопка должна обновиться.
            delivery=page.locator('[data-test-order="101"]')
            delivery.locator('p').nth(1).evaluate("p=>p.textContent='Почта России'")
            expect(delivery.get_by_text('Напечатать отправительный код',exact=True)).to_be_visible()
            delivery.locator('p').nth(1).evaluate("p=>p.textContent='Самовывоз'")
            expect(delivery.get_by_text('Напечатать отправительный код',exact=True)).to_have_count(0)
            # Статусы используют цвета CRM, подтверждение и штатные серверные переходы.
            target=Path(settings.BASE_DIR)/'outputs/avito_orders_20261101'
            target.mkdir(exist_ok=True)
            shipment=panel.get_by_label('Доставка CRM')
            payment=panel.get_by_label('Оплата CRM')
            expect(shipment).to_have_value('created')
            expect(shipment).to_have_css('background-color','rgb(231, 235, 239)')
            expect(payment).to_have_css('background-color','rgb(251, 224, 229)')
            for value,color in [('assembled','rgb(223, 236, 255)'),('delivered','rgb(219, 242, 229)')]:
                shipment.select_option(value)
                dialog=panel.get_by_role('dialog')
                expect(dialog).to_be_visible()
                self.assertNotEqual(run(lambda:Sale.objects.get().order_status),value)
                dialog.get_by_role('button',name='Подтвердить',exact=True).click()
                expect(dialog).not_to_be_visible()
                expect(shipment).to_have_value(value)
                expect(shipment).to_have_css('background-color',color)
                if value=='assembled':panel.screenshot(path=str(target/'sale_controls_assembled.png'))
            payment.select_option('paid')
            panel.get_by_role('dialog').get_by_role('button',name='Подтвердить',exact=True).click()
            expect(payment).to_have_value('paid')
            expect(payment).to_have_css('background-color','rgb(219, 242, 229)')
            self.assertTrue(run(lambda:Sale.objects.get().is_completed))
            panel.screenshot(path=str(target/'sale_controls_paid.png'))
            # «Удалить» подтверждает отмену, возвращает товар и сохраняет историю/связь.
            panel.get_by_role('button',name='Удалить продажу',exact=True).click()
            dialog=panel.get_by_role('dialog')
            dialog.get_by_role('button',name='Назад',exact=True).click()
            self.assertFalse(run(lambda:Sale.objects.get().is_cancelled))
            panel.get_by_role('button',name='Удалить продажу',exact=True).click()
            dialog.get_by_label('Причина отмены').fill('Тестовый возврат')
            dialog.get_by_role('button',name='Отменить продажу с возвратом',exact=True).click()
            expect(panel.get_by_text('Продажа отменена',exact=True)).to_be_visible()
            expect(row).to_have_attribute('data-resource-order-state','cancelled')
            expect(row).to_have_css('background-color','rgb(253, 232, 232)')
            expect(panel.get_by_text('Продажа отменена',exact=True)).to_have_css('background-color','rgb(251, 224, 229)')
            expect(panel.get_by_role('link')).to_contain_text('отменена')
            self.assertTrue(run(lambda:Sale.objects.get().is_cancelled))
            self.assertEqual(run(lambda:CDWarehouseStock.objects.get(cd=game,warehouse=wh).quantity),3)
            self.assertEqual(run(lambda:AvitoBrowserOrder.objects.get().sale_id),run(lambda:Sale.objects.get().pk))
            self.assertEqual(run(lambda:Sale.objects.count()),1)
            target=Path(settings.BASE_DIR)/'outputs/avito_orders_20261101'
            target.mkdir(exist_ok=True)
            page.screenshot(path=str(target/'browser_orders.png'),full_page=True)
            context.close()
