"""Сканер и подтверждённая печать на отдельной тестовой БД, без рабочего API и принтера."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright, expect

from accounts.models import User
from catalog.models import CD, Platform, BarcodeRegistry
from warehouse.models import Warehouse
from yandex_market.models import Integration, OrderMetadata, OrderLine, RemoteOffer, OfferConnection, SyncJob
from sales.models import Sale, SaleCDItem, MarketPrintJob, MarketScanEvent
from sales.market_browser_checks import database_call
from sales.market_fulfillment import process_print_jobs
from sales.test_label_printing import label_pdf


class MarketScanBrowserChecks(StaticLiveServerTestCase):
    def test_scanning_complete_oldest_order_waits_for_printing_before_ready(self):
        actor = User.objects.create_superuser('scanner-browser')
        self.client.force_login(actor)
        warehouse = Warehouse.objects.create(name='Scan test warehouse')
        integration = Integration.objects.create(business_id=100, campaign_id=200, enabled=True,
            fulfillment_warehouse=warehouse, operator=actor)
        platform = Platform.objects.create(name='PS5')
        products = [CD.objects.create(name=f'Scan game {i}', platform=platform) for i in range(2)]
        barcodes = ['0000000012345', '0000000054321']
        connections = []
        for index, product in enumerate(products):
            BarcodeRegistry.objects.create(value=barcodes[index], cd=product, product_kind='cd')
            remote = RemoteOffer.objects.create(integration=integration, offer_id=str(index))
            connections.append(OfferConnection.objects.create(integration=integration, remote_offer=remote, cd=product))
        orders = []
        for number, age, counts in [(300, 2, (2, 1)), (200, 0, (1, 0))]:
            sale = Sale.objects.create(warehouse=warehouse, created_by=actor, price_type='yandex_market',
                sale_type='yandex_market', payment_method='bank_transfer_postpay')
            order = OrderMetadata.objects.create(integration=integration, sale=sale, order_id=number,
                status='PROCESSING', substatus='STARTED', created_remote_at=timezone.now() - timedelta(days=age),
                items=[{'id': index + 1, 'count': count} for index, count in enumerate(counts) if count])
            for index, count in enumerate(counts):
                if count:
                    OrderLine.objects.create(order=order, connection=connections[index], remote_item_id=index + 1, quantity=count, unit_price=10)
                    SaleCDItem.objects.create(sale=sale, cd=products[index], quantity=count, unit_price=10,
                        line_total=count * 10, unit_cost_snapshot=1, product_name_snapshot=products[index].name, article_snapshot='x')
            orders.append(order)
        output = Path(settings.BASE_DIR) / 'outputs/market_scan_fulfillment_20261020/browser-scanner'
        output.mkdir(parents=True, exist_ok=True)
        with override_settings(MEDIA_ROOT=output / 'media'), ThreadPoolExecutor(max_workers=1) as database, \
                patch('sales.market_fulfillment.printer_configuration', return_value='Test printer'), \
                patch('sales.market_fulfillment.print_pdf', return_value=77) as printer, \
                patch('sales.market_fulfillment.print_job_completed', return_value=False) as printed, \
                patch('sales.market_fulfillment.release_print_job'), \
                patch('yandex_market.client.YandexMarketClient.call', side_effect=AssertionError('API запрещён в браузерном тесте')), \
                sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch(channel='chromium')
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script("window.print=()=>{throw Error('Browser print forbidden')}; window.open=()=>{throw Error('New page forbidden')};")
            page.goto(self.live_server_url + reverse('sales:incomplete'))
            original_url = page.url
            status = page.locator('#market-scan-status')
            expect(status).to_be_visible()
            page.evaluate("const input=document.createElement('input'); input.id='normal-input'; document.body.appendChild(input); input.focus();")
            page.keyboard.type(barcodes[0], delay=5)
            page.keyboard.press('Enter')
            self.assertEqual(run(lambda: MarketScanEvent.objects.count()), 0)
            page.evaluate("document.getElementById('normal-input').remove()")
            for barcode, quantity in [(barcodes[0], 1), (barcodes[0], 2)]:
                page.keyboard.type(barcode, delay=5)
                page.keyboard.press('Enter')
                expect(status).to_contain_text(f'{quantity} из 3')
                self.assertEqual(run(lambda: MarketPrintJob.objects.count()), 0)
            page.keyboard.type(barcodes[1], delay=5)
            page.keyboard.press('Enter')
            expect(status).to_contain_text('Заказ №300')
            expect(status).to_contain_text('Печатаем')
            self.assertEqual(run(lambda: MarketPrintJob.objects.count()), 1)
            job = run(lambda: MarketPrintJob.objects.get())
            self.assertEqual(job.order_id, orders[0].pk)
            run(process_print_jobs)
            def finish_refresh():
                current = MarketPrintJob.objects.get(pk=job.pk)
                current.refresh_job.state = 'done'
                current.refresh_job.save(update_fields=['state'])
            run(finish_refresh)
            run(process_print_jobs)
            def finish_boxes():
                current = MarketPrintJob.objects.get(pk=job.pk)
                self.assertEqual(current.boxes_job.payload['boxes'], [{'items': [{'id': 1, 'fullCount': 2}, {'id': 2, 'fullCount': 1}]}])
                current.order.boxes = [{'id': 9}]
                current.order.save(update_fields=['boxes'])
                current.boxes_job.state = 'done'
                current.boxes_job.save(update_fields=['state'])
            run(finish_boxes)
            run(process_print_jobs)
            def finish_pdf():
                current = MarketPrintJob.objects.get(pk=job.pk)
                self.assertEqual(current.document.format, 'A9_HORIZONTALLY')
                current.document.file.save('test.pdf', ContentFile(label_pdf()), save=False)
                current.document.state = 'done'
                current.document.save(update_fields=['file', 'state'])
            run(finish_pdf)
            run(process_print_jobs)
            run(process_print_jobs)
            expect(status).to_contain_text('Ожидаем завершения печати', timeout=15000)
            current = run(lambda: MarketPrintJob.objects.get(pk=job.pk))
            self.assertIsNone(current.printed_at)
            self.assertIsNone(current.ready_job_id)
            self.assertEqual(printer.call_count, 1)
            page.screenshot(path=str(output / 'waiting-for-printer.png'), full_page=True)
            printed.return_value = True
            run(process_print_jobs)
            run(process_print_jobs)
            current = run(lambda: MarketPrintJob.objects.select_related('ready_job', 'order').get(pk=job.pk))
            self.assertIsNotNone(current.printed_at)
            self.assertEqual(current.ready_job.payload['action'], 'ready')
            def finish_ready():
                current.ready_job.state = 'done'
                current.ready_job.save(update_fields=['state'])
                current.order.substatus = 'READY_TO_SHIP'
                current.order.save(update_fields=['substatus'])
            run(finish_ready)
            run(process_print_jobs)
            expect(status).to_contain_text('готов к отгрузке', timeout=15000)
            self.assertEqual(printer.call_count, 1)
            page.keyboard.type(barcodes[0], delay=5)
            page.keyboard.press('Enter')
            expect(status).to_contain_text('Заказ №200')
            self.assertEqual(run(lambda: MarketPrintJob.objects.count()), 2)
            self.assertEqual(page.url, original_url)
            self.assertEqual(len(context.pages), 1)
            expect(page.locator('dialog[open]')).to_have_count(0)
            expect(page.locator('iframe')).to_have_count(0)
            page.set_viewport_size({'width': 320, 'height': 900})
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 320)
            page.screenshot(path=str(output / 'scanner-320.png'), full_page=True)
            self.assertEqual(errors, [])
            context.close()
            browser.close()
