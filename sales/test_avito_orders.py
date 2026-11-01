"""Заказы расширения: никаких реальных заказов, внешних API и физической печати."""
import base64
from io import BytesIO
from unittest.mock import patch
import uuid

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from PIL import Image
from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from integrations.models import AvitoProductProfile, AvitoRemoteListing, AvitoListingConnection


class AvitoOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('avito-orders-test')
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(name='Synthetic Avito')
        self.product = CD.objects.create(name='Synthetic game', platform=Platform.objects.create(name='Test PS5'), avito_price=100)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.product, quantity=5)
        profile = AvitoProductProfile.objects.create(cd=self.product)
        listing = AvitoRemoteListing.objects.create(avito_item_id=123, title='Synthetic listing')
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        self.payload = dict(order_id='70000000000000001', titles=['Synthetic listing'],
                            carrier='Почта России', amount='100.00', status='Отправьте заказ')

    def test_draft_only_prefills_and_reuses_order_without_sale_or_stock_changes(self):
        from .avito_orders import prepare_order, initial_lines
        from .models import Sale
        first = prepare_order(self.payload, self.user)
        self.assertEqual(prepare_order(self.payload, self.user).pk, first.pk)
        self.assertFalse(Sale.objects.exists())
        self.assertEqual(self.product.warehouse_stocks.get().quantity, 5)
        self.assertEqual(initial_lines(first)[0]['product_id'], self.product.pk)
        self.assertEqual(initial_lines(first)[0]['prices']['retail'], '100.00')

    def test_confirm_creates_one_sale_and_repeat_never_deducts_twice(self):
        from .avito_orders import prepare_order
        from .models import Sale
        order = prepare_order(self.payload, self.user)
        url = reverse('sales:avito_create', args=[order.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sale.objects.exists())
        data = dict(warehouse=self.warehouse.pk, note='Test', product_type='cd', product_id=self.product.pk,
                    quantity=1, unit_discount=0, payment_method='bank_transfer_postpay', sale_type='avito', price_type='retail')
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(self.product.warehouse_stocks.get().quantity, 4)
        self.assertEqual(order.sale.sale_type, 'avito')
        self.assertFalse(order.sale.is_completed)

    def test_api_requires_csrf_permissions_and_blocks_test_environment(self):
        url = reverse('sales:avito_bridge')
        anonymous = Client(enforce_csrf_checks=True)
        self.assertEqual(anonymous.post(url, {}, content_type='application/json').status_code, 403)
        with override_settings(GAMEBAT_ENV='local_test'):
            self.assertEqual(self.client.post(url, {'action':'draft', 'order':self.payload}, content_type='application/json').status_code, 403)
        self.user.is_superuser = False
        self.user.save()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_cancelled_order_and_unknown_title_do_not_create_phantom_products(self):
        from .avito_orders import prepare_order, initial_lines
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            prepare_order({**self.payload, 'status':'Отменён'}, self.user)
        order = prepare_order({**self.payload, 'titles':['No such product']}, self.user)
        self.assertEqual(initial_lines(order), [])
        self.assertEqual(CD.objects.count(), 1)

    def test_authenticated_bridge_still_requires_csrf_and_preserves_long_order_id(self):
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        url=reverse('sales:avito_bridge')
        response=strict.get(url)
        self.assertEqual(response.status_code,200)
        payload={'action':'draft','order':self.payload}
        self.assertEqual(strict.post(url,payload,content_type='application/json').status_code,403)
        csrf=strict.cookies['csrftoken'].value
        self.assertEqual(strict.post(url,payload,content_type='application/json',HTTP_X_CSRFTOKEN=csrf).status_code,200)
        from .models import AvitoBrowserOrder
        self.assertEqual(AvitoBrowserOrder.objects.get().external_id,self.payload['order_id'])

    def linked_sale(self, payment_method='bank_transfer_postpay'):
        from .services import create_sale
        from .avito_orders import prepare_order
        sale=create_sale(actor=self.user,warehouse_id=self.warehouse.pk,sale_type='avito',
            price_type='retail',payment_method=payment_method,
            lines=[dict(product_type='cd',product_id=self.product.pk,quantity=1,unit_discount=0)])
        order=prepare_order(self.payload,self.user);order.sale=sale;order.save(update_fields=['sale'])
        return order,sale

    def test_extension_statuses_follow_crm_transitions_and_reject_stale_updates(self):
        order,sale=self.linked_sale()
        url=reverse('sales:avito_bridge')
        post=lambda data:self.client.post(url,data,content_type='application/json')
        info=post({'action':'lookup','ids':[order.external_id]}).json()
        state=info['orders'][order.external_id]['sale']
        self.assertEqual(state['order_status'],'created');self.assertEqual(state['next_order'],'assembled')
        self.assertIn('.sale-status-created',info['status_css'])
        data=dict(action='sale_status',order_id=order.external_id,field='order',value='assembled',version=state['version'],confirmed=True)
        self.assertEqual(post({**data,'confirmed':False}).status_code,400)
        self.assertEqual(post({**data,'value':'delivered'}).status_code,400)
        changed=post(data)
        self.assertEqual(changed.status_code,200)
        self.assertEqual(changed.json()['order']['sale']['order_status'],'assembled')
        self.assertEqual(post(data).status_code,409)
        self.assertEqual(self.product.warehouse_stocks.get().quantity,4)

    def test_extension_payment_is_a_single_real_payment_and_checks_action_permissions(self):
        from django.contrib.auth.models import Permission
        from .models import Sale
        from cash.models import CashTransaction
        order,sale=self.linked_sale('cash_postpay')
        url=reverse('sales:avito_bridge')
        data=dict(action='sale_status',order_id=order.external_id,field='payment',value='paid',
                  version=sale.updated_at.isoformat(),confirmed=True)
        limited=User.objects.create_user('extension-no-status-right')
        limited.user_permissions.add(*Permission.objects.filter(content_type__app_label='sales',codename__in=['create_sale','view_sales']))
        self.client.force_login(limited)
        self.assertEqual(self.client.post(url,data,content_type='application/json').status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url,data,content_type='application/json').status_code,200)
        sale.refresh_from_db();self.assertEqual(sale.payment_status,Sale.PaymentStatus.PAID)
        self.assertEqual(sale.cash_received_amount,100)
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(),1)
        self.assertEqual(self.client.post(url,data,content_type='application/json').status_code,409)
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(),1)
        self.assertEqual(self.product.warehouse_stocks.get().quantity,4)

    def test_extension_cancel_returns_stock_and_refunds_once_without_deleting_history(self):
        from cash.models import CashTransaction
        from .services import mark_sale_paid
        from .models import AvitoBrowserOrder, Sale
        order,sale=self.linked_sale('cash_postpay')
        sale=mark_sale_paid(actor=self.user,sale_id=sale.pk)
        data=dict(action='cancel_sale',order_id=order.external_id,version=sale.updated_at.isoformat(),
                  confirmed=True,comment='Покупатель отказался')
        url=reverse('sales:avito_bridge')
        post=lambda data:self.client.post(url,data,content_type='application/json')
        self.assertEqual(post({**data,'confirmed':False}).status_code,400)
        self.assertEqual(post({**data,'comment':''}).status_code,400)
        result=post(data)
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.json()['order']['cancelled'])
        self.assertEqual(self.product.warehouse_stocks.get().quantity,5)
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(),2)
        self.assertTrue(Sale.objects.filter(pk=sale.pk,cancelled_at__isnull=False).exists())
        self.assertEqual(AvitoBrowserOrder.objects.get(pk=order.pk).sale_id,sale.pk)
        self.assertEqual(post(data).status_code,409)
        self.assertEqual(self.product.warehouse_stocks.get().quantity,5)
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(),2)

    def test_extension_cancel_requires_own_permission_and_only_uses_linked_order(self):
        from django.contrib.auth.models import Permission
        order,sale=self.linked_sale()
        limited=User.objects.create_user('extension-can-read-only')
        limited.user_permissions.add(*Permission.objects.filter(content_type__app_label='sales',codename__in=['create_sale','view_sales']))
        self.client.force_login(limited)
        url=reverse('sales:avito_bridge')
        post=lambda data:self.client.post(url,data,content_type='application/json')
        state=post(dict(action='lookup',ids=[order.external_id])).json()['orders'][order.external_id]['sale']
        self.assertFalse(state['can_cancel']);self.assertFalse(state['can_mark_paid']);self.assertIsNone(state['next_order'])
        data=dict(action='cancel_sale',order_id=order.external_id,confirmed=True,comment='Test',version=sale.updated_at.isoformat())
        self.assertEqual(post(data).status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(post({**data,'order_id':'99999999999999999','sale_id':sale.pk}).status_code,404)
        sale.refresh_from_db();self.assertFalse(sale.is_cancelled)
        self.assertEqual(self.product.warehouse_stocks.get().quantity,4)

    def test_native_shipping_spool_is_not_print_confirmation(self):
        from .avito_shipping import request_label, process_jobs
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media,LABEL_PRINT_BACKEND='native'), patch('sales.market_fulfillment.printer_configuration',return_value='Fake'):
            data=dict(request_id=str(uuid.uuid4()),order=self.payload,symbol={'type':'128','content':'00123456789012'})
            job=request_label(actor=self.user,data=data)
            with patch('sales.label_printing.print_pdf',return_value=77) as spool, patch('sales.label_printing.print_job_completed',return_value=False) as completed:
                process_jobs();process_jobs()
                spool.assert_called_once()
                completed.assert_called_once()
                job.refresh_from_db();self.assertIsNone(job.printed_at);self.assertEqual(job.state,'spooled')
            with patch('sales.label_printing.print_job_completed',return_value=True),patch('sales.label_printing.release_print_job',side_effect=OSError('cleanup only')):
                process_jobs()
            job.refresh_from_db();self.assertEqual(job.state,'done')

    def test_label_is_58x40_rejects_invalid_images_and_does_not_fetch_urls(self):
        from .avito_shipping import label_pdf
        import pymupdf
        image = BytesIO()
        Image.new('RGB', (840,335), 'white').save(image, 'PNG')
        encoded = base64.b64encode(image.getvalue()).decode()
        pdf = label_pdf(encoded, 'Почта России')
        with pymupdf.open(stream=pdf, filetype='pdf') as doc:
            self.assertAlmostEqual(doc[0].rect.width*25.4/72, 58, places=2)
            self.assertAlmostEqual(doc[0].rect.height*25.4/72, 40, places=2)
            self.assertIn('Почта', doc[0].get_text())
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            label_pdf('https://example.com/label.png', 'СДЭК')

    @override_settings(LABEL_PRINT_BACKEND='agent')
    def test_shipping_agent_queue_confirms_only_after_print_and_preserves_sale(self):
        from .avito_shipping import request_label
        from .models import PrintAgent, AvitoShippingPrintJob
        import hashlib
        token='test-shipping-agent-with-no-live-credentials'
        agent=PrintAgent.objects.create(name='Shipping fake',printer_name='Fake printer',token_hash=hashlib.sha256(token.encode()).hexdigest())
        image=BytesIO();Image.new('RGB',(840,335),'white').save(image,'PNG')
        request=dict(request_id=str(uuid.uuid4()),order=self.payload,image=base64.b64encode(image.getvalue()).decode())
        with self.settings(MEDIA_ROOT=self.enterContext(__import__('tempfile').TemporaryDirectory())):
            job=request_label(actor=self.user,data=request)
            self.assertEqual(request_label(actor=self.user,data=request).pk,job.pk)
            # И новое нажатие не дублирует ещё не завершённую печать.
            self.assertEqual(request_label(actor=self.user,data={**request,'request_id':str(uuid.uuid4())}).pk,job.pk)
            session=str(uuid.uuid4())
            headers={'HTTP_HOST':'127.0.0.1','HTTP_AUTHORIZATION':'Bearer '+token,'HTTP_X_PRINT_AGENT':str(agent.pk),'HTTP_X_PRINT_SESSION':session,'HTTP_X_PRINT_PROTOCOL':'1'}
            post=lambda path,data:self.client.post('/crm/print-agent/'+path+'/',data,content_type='application/json',**headers)
            self.assertEqual(post('heartbeat',dict(version='1.0.0',printer_name=agent.printer_name,printer_available=True)).status_code,200)
            offer=post('claim',{}).json()['job']
            self.assertEqual(offer['id'],str(job.request_id))
            result=dict(claim=offer['claim'],sha256=offer['sha256'])
            self.assertEqual(post('jobs/'+offer['id']+'/result',{**result,'state':'begin'}).status_code,200)
            self.assertEqual(post('jobs/'+offer['id']+'/result',{**result,'state':'spooled','spool_job_id':77}).status_code,200)
            job.refresh_from_db();self.assertIsNone(job.printed_at)
            self.assertEqual(post('jobs/'+offer['id']+'/result',{**result,'state':'confirmed','spool_job_id':77}).status_code,200)
            job.refresh_from_db();self.assertEqual(job.state,'done');self.assertIsNotNone(job.printed_at)
            self.assertEqual(AvitoShippingPrintJob.objects.count(),1)
            self.assertIsNone(job.order.sale_id)
            self.assertEqual(self.product.warehouse_stocks.get().quantity,5)
