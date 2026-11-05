"""Техника и независимые географии, без ReefAPI или изменения учётных цен."""
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from catalog.models import Tech,Brand,ProductType
from integrations.models import AvitoManualPrice
from warehouse.models import TechWarehouseStock
from integrations.avito_check import manual_search_url
from price.models import ProcurementPriceList, ProcurementPriceListItem
from partners.models import Supplier
from warehouse.models import Warehouse, CDWarehouseStock
from .avito_check_catalog import listed_products, import_costs, found_prices
from .test_avito_check_list import AvitoCheckListTests


class AvitoScopesTests(AvitoCheckListTests):
    def tech(self):
        tech=Tech.objects.create(name='Sony DualSense White',brand=Brand.objects.create(name='Sony'),
            product_type=ProductType.objects.create(name='Геймпады'),cost=3000)
        self.link(tech,998);TechWarehouseStock.objects.create(tech=tech,warehouse=self.warehouse,quantity=3)
        return tech

    def test_tech_and_cd_share_physical_list_and_two_stage_queue(self):
        tech=self.tech()
        response=self.client.get(reverse('pricing:avito_check'))
        self.assertContains(response,tech.name);self.assertEqual(response.context['total'],2)
        self.assertContains(response,'Глобальный остаток');self.assertContains(response,'Себестоимость из прайса, ₽')
        data=self.client.get(reverse('pricing:avito_check_manual_context')).json()['items']
        self.assertEqual({(i['kind'],i['id'],i['scope']) for i in data},
            {('cd',self.cd.pk,'russia'),('cd',self.cd.pk,'rostov'),('tech',tech.pk,'russia'),('tech',tech.pk,'rostov')})

    def test_scopes_preserve_each_price_version_and_author(self):
        for scope,amount in [('russia','3500'),('rostov','3000')]:
            response=self.save_price(amount,scope=scope,expected_recorded_at='')
            self.assertEqual(response.status_code,200)
        first=AvitoManualPrice.objects.get(profile=self.profile,scope='russia')
        second=AvitoManualPrice.objects.get(profile=self.profile,scope='rostov')
        second_snapshot=(second.price,second.recorded_at,second.recorded_by_id)
        response=self.save_price('3600',scope='russia',expected_recorded_at=first.recorded_at.isoformat())
        self.assertEqual(response.status_code,200);self.assertTrue(response.json()['warning'])
        second.refresh_from_db()
        self.assertEqual((second.price,second.recorded_at,second.recorded_by_id),second_snapshot)
        self.assertEqual(self.save_price('3100',scope='rostov',expected_recorded_at=second.recorded_at.isoformat()).status_code,200)
        self.assertEqual(self.save_price('3200',scope='rostov',expected_recorded_at=second.recorded_at.isoformat()).status_code,409)
        self.assertEqual(self.save_price('3300',scope='invalid').status_code,400)

    def test_legacy_extension_without_type_or_scope_is_rejected(self):
        self.assertEqual(self.client.post(reverse('pricing:avito_check_found_price'),{
            'kind':'cd','product_id':self.cd.pk,'price':'1000','manual_queue':'1','expected_recorded_at':''}).status_code,400)
        self.assertEqual(self.client.get(reverse('pricing:avito_check_manual_context'),{'product_id':self.cd.pk}).status_code,400)

    def test_profile_without_connection_and_zero_stock_tech_are_excluded(self):
        from integrations.models import AvitoProductProfile
        tech=self.tech()
        stock=tech.warehouse_stocks.get();stock.quantity=0;stock.save(update_fields=('quantity',))
        unlinked=Tech.objects.create(name='Техника без связи',brand=tech.brand,product_type=tech.product_type)
        AvitoProductProfile.objects.create(tech=unlinked)
        TechWarehouseStock.objects.create(tech=unlinked,warehouse=self.warehouse,quantity=9)
        self.assertEqual([(p._meta.model_name,p.pk) for p in listed_products()],[('cd',self.cd.pk)])

    def test_physical_stock_is_global_and_prefetch_does_not_grow_per_product(self):
        tech=self.tech()
        second=Warehouse.objects.create(name='Второй физический склад')
        CDWarehouseStock.objects.create(cd=self.cd,warehouse=second,quantity=4)
        with self.assertNumQueries(4):
            products=listed_products()
            for product in products:found_prices(product)
        self.assertEqual({(p._meta.model_name,p.pk):p.physical_stock for p in products},
            {('cd',self.cd.pk):5,('tech',tech.pk):3})

    def test_import_cost_uses_only_latest_ordinary_list_without_markup_or_fallback(self):
        tech=self.tech()
        supplier=Supplier.objects.create(name='Тестовый',letter='A')
        def price(*,addition=False):
            return ProcurementPriceList.objects.create(created_by=self.user,exchange_rate_aed_rub=25,
                is_trip_addition=addition)
        def item(version,product,base,delivery):
            return ProcurementPriceListItem.objects.create(price_list=version,product_kind=product._meta.model_name,
                **{product._meta.model_name:product},product_name_snapshot=product.name,
                article_snapshot='',selected_supplier=supplier,supplier_price_aed=10,exchange_rate_aed_rub=25,
                base_price_rub=base,delivery_rub=delivery,markup_rub=999,
                prepayment_price_rub=9999,postpayment_price_rub=10001)
        older=price();item(older,self.cd,100,10);item(older,tech,200,20)
        latest=price();item(latest,self.cd,Decimal('500.25'),Decimal('14.50'))
        addition=price(addition=True);item(addition,self.cd,999,99)
        with self.assertNumQueries(2):selected,costs=import_costs()
        self.assertEqual(selected.pk,latest.pk)
        self.assertEqual(costs,{('cd',self.cd.pk):Decimal('514.75')})
        response=self.client.get(reverse('pricing:avito_check'))
        tech_row=next(r for r in response.context['rows'] if r['kind']=='tech')
        self.assertIsNone(tech_row['import_cost'])
        self.assertEqual(self.cd.cost,Decimal('3000'))

    def test_geography_urls_keep_media_filters_only_for_discs(self):
        from urllib.parse import urlsplit,parse_qs
        tech=self.tech()
        cd_rf=urlsplit(manual_search_url(self.cd,'cd','russia'))
        cd_city=urlsplit(manual_search_url(self.cd,'cd','rostov'))
        self.assertTrue(cd_rf.path.startswith('/all/'))
        self.assertTrue(cd_city.path.startswith('/rostov-na-donu/'))
        self.assertEqual(cd_rf.query,cd_city.query)
        self.assertIn('f',parse_qs(cd_rf.query))
        tech_url=urlsplit(manual_search_url(tech,'tech','rostov'))
        self.assertEqual(tech_url.path,'/rostov-na-donu')
        self.assertNotIn('f',parse_qs(tech_url.query))
