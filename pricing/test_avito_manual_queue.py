"""Очередь расширения использует список Avito Check и существующий аудит найденной цены."""
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import CD, BarcodeRegistry, ProductChangeEvent
from integrations.models import AvitoManualPrice
from warehouse.models import CDWarehouseStock
from . import test_avito_check_list as fixtures


class AvitoManualQueueTests(TestCase):
    setUp = fixtures.AvitoCheckListTests.setUp
    link = fixtures.AvitoCheckListTests.link
    save_price = fixtures.AvitoCheckListTests.save_price

    def context_url(self):
        return reverse('pricing:avito_check_manual_context')

    def test_context_prefills_manual_price_and_never_uses_selling_price(self):
        self.save_price('3450.25')
        response = self.client.get(self.context_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        item = response.json()['items'][0]
        self.assertEqual((item['id'], item['price']), (self.cd.pk, '3450.25'))
        self.assertTrue(item['recorded_at'])
        self.assertTrue(item['search_url'].startswith('https://www.avito.ru/'))
        self.assertNotIn('csrf_token', item)
        AvitoManualPrice.objects.all().delete()
        item = self.client.get(self.context_url(), {'product_id':self.cd.pk}).json()['product']
        self.assertEqual((item['price'], item['recorded_at']), ('', ''))

    def test_queue_search_order_and_stock_link_guards(self):
        other = CD.objects.create(name='AAA Game', platform=self.cd.platform)
        self.link(other, 456)
        CDWarehouseStock.objects.create(cd=other, warehouse=self.warehouse, quantity=1)
        AvitoManualPrice.objects.create(profile=other.avito_profile, price=1,
            recorded_at=timezone.now(), recorded_by=self.user)
        self.assertEqual([p['id'] for p in self.client.get(self.context_url()).json()['items']], [other.pk,self.cd.pk])
        self.assertEqual([p['id'] for p in self.client.get(self.context_url(), {'sort':'newest'}).json()['items']], [other.pk,self.cd.pk])
        BarcodeRegistry.objects.create(product_kind='cd', cd=self.cd, value='0012345600')
        self.assertEqual([p['id'] for p in self.client.get(self.context_url(), {'q':'0012345600'}).json()['items']], [self.cd.pk])
        stock = self.cd.warehouse_stocks.get()
        stock.quantity=0
        stock.save(update_fields=('quantity',))
        self.assertEqual(self.client.get(self.context_url(), {'product_id':self.cd.pk}).status_code,404)
        other.avito_profile.connection.delete()
        self.assertEqual(self.client.get(self.context_url()).json()['items'],[])

    def test_extension_save_checks_version_and_current_eligibility(self):
        self.assertEqual(self.save_price('3450', manual_queue='1').status_code, 400)
        payload={'manual_queue':'1', 'expected_recorded_at':''}
        self.assertEqual(self.save_price('3450', **payload).status_code,200)
        before=AvitoManualPrice.objects.get(profile=self.profile)
        events=ProductChangeEvent.objects.filter(cd=self.cd).count()
        self.assertEqual(self.save_price('3550', **payload).status_code,409)
        self.assertEqual(ProductChangeEvent.objects.filter(cd=self.cd).count(),events)
        before.refresh_from_db()
        self.assertEqual(str(before.price),'3450.00')
        self.assertEqual(self.save_price('3550',manual_queue='1',expected_recorded_at=before.recorded_at.isoformat()).status_code,200)
        stock=self.cd.warehouse_stocks.get()
        stock.quantity=0
        stock.save(update_fields=('quantity',))
        self.assertEqual(self.save_price('3650', **payload).status_code,404)

    def test_extension_context_needs_price_permissions_and_save_needs_csrf(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        viewer=get_user_model().objects.create_user('manual-viewer')
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='pricing',codename='view_pricing'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.context_url()).status_code,403)
        anonymous=Client()
        self.assertEqual(anonymous.get(self.context_url()).status_code,302)
        guarded=Client(enforce_csrf_checks=True)
        guarded.force_login(self.user)
        data=guarded.get(self.context_url()).json()
        self.assertTrue(data['csrf_token'])
        url=reverse('pricing:avito_check_found_price')
        payload={'kind':'cd','product_id':self.cd.pk,'price':'100','manual_queue':'1','expected_recorded_at':''}
        self.assertEqual(guarded.post(url,payload).status_code,403)
        self.assertEqual(guarded.post(url,payload,HTTP_X_CSRFTOKEN=data['csrf_token']).status_code,200)
