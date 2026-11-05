"""Ручная AED относится к версии и поставщику, исходные предложения неизменны."""
import json
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
from django.apps import apps
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db import connection
from django.test.utils import CaptureQueriesContext
from accounts.models import User
from django.contrib.auth.models import Permission
from orders.models import CustomerProcurementOrder
from orders.services import create_customer_procurement_order
from orders.trips import create_trip
from uuid import uuid4
from .test_procurement_suppliers import ProcurementSupplierTests
from .procurement_suppliers import prepare_supplier_choices, supplier_base_price


class ManualProcurementPriceTests(ProcurementSupplierTests):
    def manual_rows(self, letter='A', value='12.50', enabled=True):
        item=self.price.items.select_related('selected_supplier').prefetch_related(
            'supplier_offers__supplier').get()
        prepare_supplier_choices([item],self.price)
        return self.rows(letter, pricing_initial=getattr(item,'pricing_initial',''),
            manual_prices={str(self.suppliers[letter].pk):{'enabled':enabled,'price_aed':value}})

    def overrides(self):
        return apps.get_model('price','ProcurementSupplierPriceOverride').objects.filter(price_list_item=self.item)

    def test_manual_price_preserves_offer_and_reaches_stock_order_and_trip(self):
        self.update(self.manual_rows())
        self.item.refresh_from_db()
        self.assertEqual(self.item.supplier_price_aed,Decimal('12.50'))
        self.assertEqual(self.item.supplier_offers.get(supplier=self.suppliers['A']).price_aed,Decimal('10'))
        self.assertEqual(self.item.base_price_rub,supplier_base_price(self.item,self.price,Decimal('12.50')))
        self.assertEqual(self.item.configured_markup_rub,Decimal('123.45'))
        override=self.overrides().get()
        self.assertTrue(override.active);self.assertEqual(override.updated_by,self.actor)
        order=create_customer_procurement_order(actor=self.actor,price_list_id=self.price.pk,
            recipient='На склад',comment='',purpose=CustomerProcurementOrder.Purpose.STOCK,
            lines=[{'price_list_item_id':self.item.pk,'prepayment_quantity':2,'postpayment_quantity':0}])
        line=order.items.get()
        self.assertEqual(line.supplier_price_aed_snapshot,Decimal('12.50'))
        trip=create_trip(actor=self.actor,order_ids=[order.pk],creation_key=uuid4())
        self.assertEqual(trip.lines.get().supplier_price_aed_snapshot,Decimal('12.50'))
        with self.assertRaisesMessage(ValidationError,'использован в заказе'):
            self.update(self.manual_rows(value='14'))

    def test_switching_restores_each_supplier_and_disable_ignores_submitted_price(self):
        self.update(self.manual_rows());self.item.refresh_from_db()
        self.update(self.rows('F'));self.item.refresh_from_db()
        self.assertEqual(self.item.supplier_price_aed,Decimal('15'))
        self.update(self.rows('A'));self.item.refresh_from_db()
        self.assertEqual(self.item.supplier_price_aed,Decimal('12.50'))
        self.update(self.manual_rows(value='NaN',enabled=False));self.item.refresh_from_db()
        self.assertEqual(self.item.supplier_price_aed,Decimal('10'))
        self.assertFalse(self.overrides().get().active)
        self.update(self.manual_rows(value='11'));self.update(self.manual_rows(value='11'))
        self.assertEqual(self.overrides().count(),1)

    def test_invalid_values_are_atomic(self):
        for value in ('','0','-1','NaN','Infinity','1e3','1.1234567','100000000000000'):
            with self.subTest(value=value),self.assertRaises(ValidationError):self.update(self.manual_rows(value=value))
        self.item.refresh_from_db();self.assertEqual(self.item.supplier_price_aed,Decimal('9'))
        self.assertFalse(self.overrides().exists())

    def test_stale_manual_and_financial_snapshots_cannot_overwrite_new_values(self):
        stale=self.manual_rows(value='13')
        self.update(self.manual_rows())
        with self.assertRaisesMessage(ValidationError,'Обновите страницу'):self.update(stale)
        self.item.refresh_from_db();self.assertEqual(self.item.supplier_price_aed,Decimal('12.50'))
        stale=self.manual_rows();self.update(self.rows('A',markup='200'))
        with self.assertRaisesMessage(ValidationError,'Обновите страницу'):self.update(stale)

    def test_manual_permissions_are_checked_in_service_and_http(self):
        user=User.objects.create_user('only-delivery-manual')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='price',codename__in=(
            'view_price_page','view_supplier_prices','change_procurement_delivery')))
        with self.assertRaisesMessage(ValidationError,'нужны права'):self.update(self.manual_rows(),actor=user)
        self.client.force_login(user)
        response=self.client.post(reverse('price:procurement_update',args=[self.price.pk]),
            {'pricing_rows':json.dumps(self.manual_rows())},follow=True)
        self.assertContains(response,'нужны права')
        self.assertFalse(self.overrides().exists())

    def test_stock_form_uses_snapshot_prices_and_safe_labels_without_n_plus_one(self):
        self.update(self.manual_rows());self.client.force_login(self.actor)
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get(reverse('orders:stock_create'),{'price_list':self.price.pk})
        self.assertContains(response,'Цены поставщиков, AED')
        self.assertContains(response,'Ручная цена. Исходное предложение: 10 AED')
        self.assertContains(response,'A–12.5')
        self.assertEqual(sum('FROM "price_procurementsupplieroffer"' in q['sql'] for q in queries),1)
        self.assertEqual(sum('FROM "price_procurementsupplierpriceoverride"' in q['sql'] for q in queries),1)
        self.assertContains(response,'colspan="8"')
        self.assertContains(response,'data-label="Цены поставщиков, AED"')

    def test_new_version_never_imports_manual_override(self):
        self.update(self.manual_rows())
        from .services import create_procurement_price_list
        other=create_procurement_price_list(actor=self.actor,exchange_rate_usdt_aed='3.67',exchange_rate_usdt_rub=90,
            delivery_general_usdt_per_kg=0,delivery_devices_usdt_per_kg=0,delivery_storage_usdt_per_kg=0,delivery_cd_rub=5)
        self.assertEqual(other.items.get().supplier_offers.get(supplier=self.suppliers['A']).price_aed,Decimal('10'))
        self.assertEqual(other.items.get().supplier_price_aed,Decimal('9'))

    def test_python_and_js_share_conversion_vectors(self):
        vectors=json.loads(Path(__file__).with_name('procurement_conversion_cases.json').read_text())
        for vector in vectors:
            with self.subTest(vector=vector):
                price=SimpleNamespace(exchange_rate_usdt_aed=Decimal(vector.get('usdt_aed','0')),
                    exchange_rate_usdt_rub=Decimal(vector.get('usdt_rub','0')))
                item=SimpleNamespace(exchange_rate_aed_rub=Decimal(vector.get('aed_rub','0')))
                self.assertEqual(supplier_base_price(item,price,Decimal(vector['aed'])),Decimal(vector['rub']))

    def test_negative_confirmation_rolls_back_manual_overrides_and_audit(self):
        from .services import NegativeProcurementMarkup
        rows=self.manual_rows();rows[self.item.pk]['markup']='-1'
        with self.assertRaises(NegativeProcurementMarkup):self.update(rows)
        self.assertFalse(self.overrides().exists())
        self.update(rows,negative_markup_confirmed=True)
        self.assertTrue(self.overrides().get().active)

    def test_missing_snapshot_unknown_supplier_and_excluded_manual_are_rejected(self):
        rows=self.manual_rows();del rows[self.item.pk]['pricing_initial']
        with self.assertRaises(ValidationError):self.update(rows)
        rows=self.manual_rows();rows[self.item.pk]['manual_prices']={'999999':{'enabled':True,'price_aed':'1'}}
        with self.assertRaises(ValidationError):self.update(rows)
        from catalog.supplier_exclusions import set_supplier_exclusions
        set_supplier_exclusions(product=self.product,supplier_ids=[self.suppliers['A'].pk],actor=self.actor)
        with self.assertRaisesMessage(ValidationError,'исключён'):self.update(self.manual_rows())
        self.assertFalse(self.overrides().exists())

    def test_stock_form_hides_private_names_and_denies_supplier_price_permission(self):
        user=User.objects.create_user('stock-safe-manual')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='orders',codename='create_order'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('orders:stock_create')).status_code,403)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='price',codename='view_supplier_prices'))
        response=self.client.get(reverse('orders:stock_create'),{'price_list':self.price.pk})
        self.assertContains(response,'Цены поставщиков, AED')
        for supplier in self.suppliers.values():self.assertNotContains(response,supplier.name)

    def test_read_only_stock_colors_and_current_import_does_not_change_snapshot(self):
        from catalog.supplier_exclusions import set_supplier_exclusions
        from pricing.models import SupplierCDPrice
        SupplierCDPrice.objects.filter(cd=self.product).update(price=999)
        set_supplier_exclusions(product=self.product,supplier_ids=[self.suppliers['F'].pk],actor=self.actor)
        self.client.force_login(self.actor)
        response=self.client.get(reverse('orders:stock_create'),{'price_list':self.price.pk})
        row=response.context['groups'][0]['rows'][0]['item']
        offers={o['supplier'].letter:o for o in row.supplier_choices}
        self.assertEqual(offers['A']['price_aed'],Decimal('10'))
        self.assertTrue(offers['F']['excluded']);self.assertTrue(offers['F']['is_expensive'])
        self.assertContains(response,'is-excluded')
        self.assertNotContains(response,'data-supplier-select')

    def test_old_winner_only_keeps_previous_editing_behavior_without_new_offers(self):
        self.item.supplier_offers.all().delete()
        rows=self.rows('M',pricing_initial=None)
        del rows[self.item.pk]['pricing_initial']
        self.update(rows);self.item.refresh_from_db()
        self.assertEqual(self.item.supplier_price_aed,Decimal('9'))
        self.client.force_login(self.actor)
        response=self.client.get(reverse('orders:stock_create'),{'price_list':self.price.pk})
        item=response.context['groups'][0]['rows'][0]['item']
        self.assertEqual(len(item.supplier_choices),1)
        self.assertFalse(item.supplier_choices[0]['can_override'])

    def test_many_stock_rows_load_both_offer_relations_once(self):
        from catalog.models import CD
        from .models import ProcurementPriceListItem
        for index in range(6):
            product=CD.objects.create(name=f'Массовая строка {index}',platform=self.product.platform,sku=f'BULK-{index}')
            data={f.attname:getattr(self.item,f.attname) for f in self.item._meta.concrete_fields if not f.primary_key}
            data.update(cd_id=product.pk,product_name_snapshot=product.name,article_snapshot=product.sku)
            item=ProcurementPriceListItem.objects.create(**data)
            for offer in self.item.supplier_offers.all():
                item.supplier_offers.create(supplier=offer.supplier,price_aed=offer.price_aed)
        self.client.force_login(self.actor)
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get(reverse('orders:stock_create'),{'price_list':self.price.pk})
        self.assertEqual(sum(len(g['rows']) for g in response.context['groups']),7)
        for table in ('price_procurementsupplieroffer','price_procurementsupplierpriceoverride'):
            self.assertEqual(sum(f'FROM "{table}"' in q['sql'] for q in queries),1)
