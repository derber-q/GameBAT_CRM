from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from catalog.models import CD, Platform
from catalog.game_codes import requires_game_codes, normalize_game_codes, set_game_codes
from partners.models import Supplier
from warehouse.models import Warehouse, CDWarehouseStock
from .models import Supply
from .services import accept_supply, confirm_supply_price_review


class SupplyGameCodesTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_superuser('codes',password='test')
        self.cd=CD.objects.create(name='Nintendo в названии',sku='CODES',platform=Platform.objects.create(name='PlayStation 5'),weight_grams=100)
        self.supplier=Supplier.objects.create(name='Поставщик',letter='A',legal_entity='ООО',phone_1='1')
        self.warehouse=Warehouse.objects.create(name='Склад')
        self.line={'product_type':'cd','product_id':self.cd.pk,'supplier_id':self.supplier.pk,'quantity':1,'purchase_unit_cost':'100'}
        self.client.force_login(self.user)

    def test_platform_relation_and_normalization_preserve_zeroes(self):
        self.assertTrue(requires_game_codes(self.cd))
        self.assertEqual(normalize_game_codes(' ppsa 00123 ; PPSA-00123, cusa-00567\nPPSA-00124'),'PPSA-00123, CUSA-00567, PPSA-00124')
        for invalid in ('', ' ; , \n ', 'X' * 101):
            with self.assertRaises(ValidationError):normalize_game_codes(invalid)
        self.cd.platform=Platform.objects.create(name='NS2');self.cd.name='PS5'
        self.assertFalse(requires_game_codes(self.cd))

    def test_arbitrary_code_formats_preserve_text_and_leading_zeroes(self):
        for value in ('036923', 'PPSA-1', 'SLUS-00123', 'код / 0001'):
            with self.subTest(value=value):
                self.assertEqual(normalize_game_codes(value), value)
        self.assertEqual(
            normalize_game_codes(' 036923 ; 036923, Custom-00001\nPPSA-00123'),
            '036923, Custom-00001, PPSA-00123',
        )

    def test_arbitrary_code_endpoint_saves_audit_and_allows_supply_acceptance(self):
        response = self.client.post(reverse('supplies:product_codes'), {
            'product_id': self.cd.pk, 'cusa_ppsa_code': '036923, Custom-00001',
        })
        self.assertEqual(response.status_code, 200)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cusa_ppsa_code, '036923, Custom-00001')
        self.assertTrue(self.cd.change_events.filter(field_changes__field_name='cusa_ppsa_code').exists())
        supply = accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=[self.line])
        self.assertEqual(CDWarehouseStock.objects.get(cd=self.cd).quantity, 1)
        self.assertIsNotNone(supply.accepted_at)

    def test_direct_final_accept_and_pending_confirmation_cannot_bypass_missing_codes(self):
        with self.assertRaises(ValidationError):accept_supply(accepted_by=self.user,warehouse_id=self.warehouse.pk,lines=[self.line])
        self.assertFalse(Supply.objects.exists())
        supply=accept_supply(accepted_by=self.user,warehouse_id=self.warehouse.pk,lines=[self.line],defer_balance=True)
        with self.assertRaises(ValidationError):confirm_supply_price_review(actor=self.user,supply_id=supply.pk)
        self.assertFalse(CDWarehouseStock.objects.filter(cd=self.cd,quantity__gt=0).exists())
        product=set_game_codes(actor=self.user,product_id=self.cd.pk,value='PPSA-00123')
        self.assertTrue(product.change_events.filter(field_changes__field_name='cusa_ppsa_code').exists())
        confirm_supply_price_review(actor=self.user,supply_id=supply.pk)
        self.assertEqual(CDWarehouseStock.objects.get(cd=self.cd).quantity,1)

    def test_code_endpoint_permissions_and_existing_code_autocomplete(self):
        url=reverse('supplies:product_codes')
        response=self.client.post(url,{'product_id':self.cd.pk,'cusa_ppsa_code':'ppsa00123, PPSA-00123'})
        self.assertEqual(response.json()['cusa_ppsa_code'],'PPSA-00123')
        response=self.client.get(reverse('supplies:autocomplete'),{'q':self.cd.sku,'context':'supply'})
        row=response.json()['results'][0];self.assertTrue(row['requires_game_codes']);self.assertEqual(row['cusa_ppsa_code'],'PPSA-00123')
        viewer=User.objects.create_user('no-codes');self.client.force_login(viewer)
        self.assertEqual(self.client.post(url,{'product_id':self.cd.pk,'cusa_ppsa_code':'PPSA-00000'}).status_code,403)
