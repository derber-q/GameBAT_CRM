"""Изолированная проверка управления Маркетом в Chromium, без рабочего API и worker."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.db import connections
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright, expect
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from pypdf import PdfReader

from accounts.models import User
from warehouse.models import Warehouse
from yandex_market.models import Integration, OrderMetadata, SyncJob, LabelDocument
from .models import Sale, MarketPrintJob


def database_call(callback):
    try:
        return callback()
    finally:
        connections.close_all()


class MarketSaleBrowserChecks(StaticLiveServerTestCase):
    def test_market_actions_label_and_controls_after_payment(self):
        owner = User.objects.create_superuser('market-browser')
        self.client.force_login(owner)
        warehouse = Warehouse.objects.create(name='Склад теста Маркета')
        integration = Integration.objects.create(business_id=123, campaign_id=234, enabled=True,
            fulfillment_warehouse=warehouse, operator=owner)
        output = Path(settings.BASE_DIR) / 'outputs' / 'market_scan_fulfillment_20261020' / 'browser-controls'
        output.mkdir(parents=True, exist_ok=True)
        pdf = BytesIO()
        sticker = canvas.Canvas(pdf, pagesize=(58 * mm, 40 * mm))
        sticker.setFont('Helvetica', 9)
        sticker.drawString(4 * mm, 30 * mm, 'TEST LABEL 58 x 40 mm')
        sticker.rect(4 * mm, 5 * mm, 50 * mm, 18 * mm)
        sticker.showPage()
        sticker.save()
        pdf_bytes = pdf.getvalue()
        with override_settings(MEDIA_ROOT=output / 'media'), patch('sales.market_fulfillment.printer_configuration', return_value='Test printer'), ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chromium')
            for width in (320, 768, 1024, 1440):
                def create_sale_order():
                    sale = Sale.objects.create(warehouse=warehouse, created_by=owner, price_type='yandex_market',
                        sale_type='yandex_market', payment_method='bank_transfer_postpay', total_amount=100)
                    order = OrderMetadata.objects.create(integration=integration, sale=sale, order_id=10000 + width,
                        status='PROCESSING', substatus='STARTED', boxes=[{'items': [{'id': 789, 'fullCount': 1}]}])
                    MarketPrintJob.objects.create(order=order, actor=owner, printer_name='Test printer',
                        state='done', printed_at=timezone.now(), printer_job_id=1)
                    return sale, order
                sale, order = database.submit(database_call, create_sale_order).result()
                context = browser.new_context(viewport={'width': width, 'height': 900})
                context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
                page = context.new_page()
                action_requests = []
                page.on('request', lambda request: action_requests.append(request.post_data)
                    if request.method == 'POST' and request.url.endswith('/market-action/') else None)
                # Любая попытка браузерной печати — ошибка: новая печать выполняется worker.
                page.add_init_script('''
                  window.print = () => {throw new Error('Browser print is forbidden');};
                  window.open = () => {throw new Error('New page is forbidden');};
                ''')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + reverse('sales:incomplete'))
                row = page.locator(f'[data-sale-row="{sale.pk}"]')
                expect(row.locator('[data-status-field="order"]')).to_have_count(0)
                expect(row.get_by_text('В обработке', exact=True)).to_have_count(0)
                expect(row.get_by_text('Заказ и коробки Маркета', exact=True)).to_have_count(0)
                expect(row.locator('[name="action"]')).to_have_count(2)
                expect(row.locator('select[name="action"]')).to_have_count(0)
                expect(row.locator('input[type="checkbox"]')).to_have_count(0)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                cancel_button = row.get_by_role('button', name='Отменить заказ', exact=True)
                cancel_dialog = page.locator('#sale-market-cancel-dialog')
                cancel_button.click()
                expect(cancel_dialog).to_be_visible()
                expect(cancel_dialog).to_contain_text(str(order.order_id))
                self.assertEqual(len(action_requests), 0)
                cancel_dialog.get_by_role('button', name='Не отменять', exact=True).click()
                expect(cancel_dialog).not_to_be_visible()
                self.assertEqual(len(action_requests), 0)
                cancel_button.click()
                page.keyboard.press('Escape')
                expect(cancel_dialog).not_to_be_visible()
                self.assertEqual(len(action_requests), 0)
                page.screenshot(path=str(output / f'list-ready-{width}.png'), full_page=True)
                row.get_by_role('button', name='Готов к отгрузке', exact=True).click()
                page.wait_for_load_state('networkidle')
                self.assertEqual(len(action_requests), 1)
                job = database.submit(database_call, lambda: SyncJob.objects.get(kind='order_action', payload__order_id=order.order_id)).result()
                self.assertEqual(job.payload['action'], 'ready')
                database.submit(database_call, order.refresh_from_db).result()
                self.assertEqual(order.substatus, 'STARTED')

                # AJAX-замена строки оплаты сохраняет печать и подтверждение отмены.
                row.locator('[data-status-field="payment"]').select_option('paid')
                page.locator('#sale-status-dialog').get_by_role('button', name='Подтвердить', exact=True).click()
                expect(row.locator('.sale-status-paid')).to_be_visible()
                original_url = page.url
                with page.expect_response('**/market-print/'):
                    row.get_by_role('button', name='Напечатать стикер Яндекса', exact=True).click()
                expect(row.locator('[data-market-print-status]')).to_contain_text('Подготавливаем')
                print_job = database.submit(database_call, lambda: MarketPrintJob.objects.filter(order=order).latest('pk')).result()

                def complete_print():
                    current = MarketPrintJob.objects.filter(order=order).latest('pk')
                    current.state, current.printed_at, current.printer_job_id = 'done', timezone.now(), 88
                    current.save(update_fields=['state', 'printed_at', 'printer_job_id'])
                database.submit(database_call, complete_print).result()
                expect(row.locator('[data-market-print-status]')).to_contain_text('напечатан', timeout=15000)
                expect(page.locator('iframe')).to_have_count(0)
                self.assertEqual(page.url, original_url)
                self.assertEqual(len(context.pages), 1)
                expect(row.locator('[name="format"]')).to_have_count(0)
                expect(row.locator('[data-market-print] [name="confirm"]')).to_have_count(0)
                cancel_button.click()
                expect(cancel_dialog).to_be_visible()
                self.assertEqual(len(action_requests), 1)
                page.screenshot(path=str(output / f'cancel-dialog-{width}.png'), full_page=True)
                cancel_dialog.get_by_role('button', name='Да, отменить заказ', exact=True).click()
                page.wait_for_load_state('networkidle')
                self.assertEqual(len(action_requests), 2)
                cancelled = database.submit(database_call,
                    lambda: SyncJob.objects.get(kind='order_action', payload__order_id=order.order_id)).result()
                self.assertEqual(cancelled.payload['action'], 'cancel')
                page.goto(self.live_server_url + reverse('sales:detail', args=[sale.pk]))
                controls = page.locator('[data-market-order]')
                print_button = controls.get_by_role('button', name='Напечатать стикер Яндекса')
                expect(print_button).to_be_visible()
                with page.expect_response('**/market-print/'):
                    print_button.click()
                database.submit(database_call, complete_print).result()
                expect(controls.locator('[data-market-print-status]')).to_contain_text('напечатан')
                self.assertEqual(database.submit(database_call, lambda: MarketPrintJob.objects.filter(order=order).count()).result(), 3)
                expect(controls.get_by_role('button', name='Готов к отгрузке', exact=True)).to_be_visible()
                expect(controls.get_by_role('button', name='Отменить заказ', exact=True)).to_be_visible()
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                self.assertLessEqual(controls.bounding_box()['x'] + controls.bounding_box()['width'], width)
                print_button.focus()
                self.assertEqual(page.locator(':focus').text_content(), 'Напечатать стикер Яндекса')
                page.screenshot(path=str(output / f'detail-print-{width}.png'), full_page=True)
                expect(page.locator('iframe')).to_have_count(0)
                self.assertEqual(errors, [])
                context.close()
            browser.close()
