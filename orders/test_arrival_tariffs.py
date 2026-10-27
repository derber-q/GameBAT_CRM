"""Пропорции исторических тарифов дисков и разных категорий техники."""
from decimal import Decimal
from uuid import uuid4
from django.test import TestCase
from catalog.models import Tech, Brand, ProductType
from price.models import ProcurementPriceListItem
from .test_arrival import ArrivalFixture
from .services import create_customer_procurement_order
from .trips import create_trip


class ArrivalTariffTests(ArrivalFixture, TestCase):
    def tech_order(self, name, weight, tariff):
        product=Tech.objects.create(name=name,sku=name,weight_grams=weight,
            brand=Brand.objects.create(name=name),product_type=ProductType.objects.create(name=name))
        source=ProcurementPriceListItem.objects.create(price_list=self.price,product_kind='tech',tech=product,
            product_name_snapshot=name,article_snapshot=name,selected_supplier=self.supplier,
            supplier_price_aed=100,exchange_rate_aed_rub=20,base_price_rub=2000,
            delivery_rub=Decimal(weight)/1000*tariff*80,weight_grams_snapshot=weight,
            delivery_usdt_per_kg_snapshot=tariff,prepayment_price_rub=3500,postpayment_price_rub=3500)
        order=create_customer_procurement_order(actor=self.user,price_list_id=self.price.pk,purpose='stock',
            recipient='На склад',comment='',lines=[{'price_list_item_id':source.pk,'prepayment_quantity':1,'postpayment_quantity':0}])
        return product,order

    def test_different_tech_tariffs_are_preserved_instead_of_uniform_per_gram(self):
        small,a=self.tech_order('Геймпад',500,4)
        large,b=self.tech_order('Консоль',1000,1)
        self.trip=create_trip(actor=self.user,order_ids=[a.pk,b.pk],creation_key=uuid4())
        arrival=self.arrive(actual_delivery='15000')
        self.assertEqual(arrival.rows.get(tech=small).delivery_total,Decimal('10000'))
        self.assertEqual(arrival.rows.get(tech=large).delivery_total,Decimal('5000'))
        self.assertEqual(arrival.rows.get(tech=small).tariff_snapshot['algorithm'],'weight_tariff')

    def test_cd_uses_fixed_original_delivery_despite_catalog_mass(self):
        tech,a=self.tech_order('Техника',500,4)
        b=self.make_order('stock',1)
        self.cd.weight_grams=9000;self.cd.save(update_fields=['weight_grams'])
        self.trip=create_trip(actor=self.user,order_ids=[a.pk,b.pk],creation_key=uuid4())
        arrival=self.arrive(actual_delivery='500')
        self.assertEqual(arrival.rows.get(cd=self.cd).delivery_total,Decimal('300'))
        self.assertEqual(arrival.rows.get(tech=tech).delivery_total,Decimal('200'))
        self.assertEqual(arrival.rows.get(cd=self.cd).tariff_snapshot['algorithm'],'fixed_unit')

    def test_saved_cd_ruble_tariff_does_not_require_missing_historical_currency(self):
        self.price.exchange_rate_usdt_rub=None
        self.price.save(update_fields=['exchange_rate_usdt_rub'])
        arrival=self.arrive()
        self.assertTrue(all(row.preliminary_delivery==Decimal('240') for row in arrival.rows.all()))
        self.assertEqual(sum(arrival.rows.values_list('delivery_total',flat=True)),Decimal('1200'))
