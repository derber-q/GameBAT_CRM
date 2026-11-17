"""Точное чтение реестра для звукового отклика поиска без утечки цен."""
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import BarcodeRegistry, Brand, CD, Platform, ProductType, Tech


class BarcodeLookupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('barcode-admin')
        self.cd = CD.objects.create(name='Игра', sku='B-CD', barcode='0000123456789',
            platform=Platform.objects.create(name='PS5'))
        self.tech = Tech.objects.create(name='Техника', sku='B-TECH', barcode='0000987654321',
            brand=Brand.objects.create(name='Sony'), product_type=ProductType.objects.create(name='Геймпады'))
        BarcodeRegistry.objects.create(value='0000111111111', product_kind='cd', cd=self.cd)
        self.url = reverse('catalog:barcode_lookup')
        self.client.force_login(self.user)

    def test_primary_secondary_and_leading_zeros_with_no_financial_data(self):
        for value in ('0000123456789', '0000111111111', '0000987654321'):
            response = self.client.get(self.url, {'barcode':value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'found':True})
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get(self.url, {'barcode':'123456789'}).json(), {'found':False})
        self.assertEqual(self.client.get(self.url, {'barcode':str(self.cd.pk)}).json(), {'found':False})

    def test_unknown_and_archived_are_not_found(self):
        self.assertEqual(self.client.get(self.url, {'barcode':'0000999999999'}).json(), {'found':False})
        self.cd.is_archived = True
        self.cd.save(update_fields=['is_archived'])
        self.assertEqual(self.client.get(self.url, {'barcode':'0000111111111'}).json(), {'found':False})
        self.assertEqual(self.client.post(self.url, {'barcode':'0000123456789'}).status_code, 405)

    def test_permissions_and_product_kind_are_enforced(self):
        viewer = User.objects.create_user('barcode-viewer')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url, {'barcode':'0000123456789'}).status_code, 403)
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog',codename='view_cd'))
        self.assertEqual(self.client.get(self.url, {'barcode':'0000123456789'}).json(), {'found':True})
        self.assertEqual(self.client.get(self.url, {'barcode':'0000987654321'}).json(), {'found':False})

    def test_pricing_reader_has_search_feedback_without_sale_permissions(self):
        viewer = User.objects.create_user('barcode-pricing')
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='pricing',codename='view_pricing'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url, {'barcode':'0000123456789'}).json(), {'found':True})
