from decimal import Decimal as D
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, SimpleTestCase, RequestFactory
from django.urls import reverse
from accounts.models import User
from catalog.models import CD, Tech, Platform, Brand, ProductType, ProductFieldChange
from catalog.nomenclature_forms import CDCardForm, TechCardForm, product_version
from catalog.nomenclature_services import update_product_card
from catalog.product_fields import MARKUP_FIELDS
from .warnings import price_warning, product_price_warnings
from .services import update_product_prices


class PriceWarningFormulaTests(SimpleTestCase):
    def test_decimal_boundaries_nulls_and_independent_rules(self):
        cases = [
            (10199,10000,9000,200,True), (10200,10000,9000,200,False),
            (10500,10000,9000,200,False), (10000,10000,9000,200,True),
            (9500,10000,9000,200,True), (10050,10000,9000,None,False),
            (9500,9000,10000,200,True), (9950,9900,10000,200,True),
            (None,10000,9000,200,False), (10000,None,9000,200,False),
            (8000,None,9000,200,True), (10000,10000,9000,0,False),
            (9999,10000,9000,0,True), (0,0,0,0,False),
            (100,None,None,None,False), (100,0,None,200,True),
            ('100.20','100.00',0,'0.20',False), ('100.19',100,0,'0.20',True),
            (0,None,1,None,True), (100,None,100,None,False),
        ]
        for price, wholesale, cost, markup, expected in cases:
            with self.subTest(price=price,wholesale=wholesale,cost=cost,markup=markup):
                args={k:D(str(v)) if v is not None else None for k,v in
                      dict(price=price,wholesale=wholesale,cost=cost,markup=markup).items()}
                self.assertEqual(bool(price_warning(**args)), expected)

    def test_both_reasons_and_old_rule_removed(self):
        warning=price_warning(price=D(9950),wholesale=D(9900),cost=D(10000),markup=D(200))
        self.assertEqual(len(warning.splitlines()),2)
        # Former cost + 200 rule would incorrectly warn here.
        self.assertEqual(price_warning(price=D(10100),wholesale=D(9800),cost=D(10000),markup=D(200)),"")


class PriceControlTests(TestCase):
    def setUp(self):
        self.actor=User.objects.create_superuser('price-control',password='Strong!12345')
        self.cd=CD.objects.create(name='Disc',platform=Platform.objects.create(name='PS test'),cost=10000,wholesale_price=9900,avito_price=9950)
        self.tech=Tech.objects.create(name='Device',brand=Brand.objects.create(name='Brand test'),product_type=ProductType.objects.create(name='Type test'))

    def test_defaults_nulls_validation_and_audit_for_both_models(self):
        for kind,product in [('cd',self.cd),('tech',self.tech)]:
            for field in MARKUP_FIELDS:
                self.assertEqual(getattr(product,field),D(189))
            update_product_prices(actor=self.actor,product_type=kind,product_id=product.pk,changes={
                'avito_markup_from_wholesale':'','yandex_markup_from_wholesale':'350.15',
            })
            product.refresh_from_db()
            self.assertIsNone(product.avito_markup_from_wholesale)
            self.assertEqual(product.yandex_markup_from_wholesale,D('350.15'))
            self.assertTrue(ProductFieldChange.objects.filter(field_name='avito_markup_from_wholesale',new_value='').exists())
            for invalid in ('-1','NaN','Infinity'):
                with self.assertRaises(ValidationError):
                    update_product_prices(actor=self.actor,product_type=kind,product_id=product.pk,changes={'avito_markup_from_wholesale':invalid})
            with self.assertRaises(IntegrityError), transaction.atomic():
                type(product).objects.filter(pk=product.pk).update(avito_markup_from_wholesale=-1)

    def test_price_page_has_warnings_but_no_markup_inputs(self):
        self.client.force_login(self.actor)
        page=self.client.get(reverse('pricing:list'))
        self.assertContains(page,'price-warning')
        self.assertContains(page,'data-markup-for="avito_price"')
        for field in MARKUP_FIELDS:
            self.assertNotContains(page,f'name="{field}"')
        self.assertNotContains(page,'avito-low-margin')
        self.assertNotContains(page,'avito-price-input')
        for field in ('avito_price','wholesale_price','yandex_market_price'):
            response=self.client.post(reverse('pricing:product_update'),{'product_type':'cd','product_id':self.cd.pk,field:'1.00'})
            self.assertEqual(response.status_code,302)
            self.cd.refresh_from_db()
            self.assertEqual(getattr(self.cd,field),D('1.00'))
            self.assertTrue(product_price_warnings(self.cd)[field])

    def test_form_fields_permissions_and_markup_save(self):
        worker=User.objects.create_user('price-editor')
        worker.user_permissions.add(Permission.objects.get(codename='change_retail_price'))
        for kind,product,form_class in [('cd',self.cd,CDCardForm),('tech',self.tech,TechCardForm)]:
            product.refresh_from_db()
            form=form_class(instance=product,user=worker)
            self.assertFalse(form.fields['avito_markup_from_wholesale'].disabled)
            self.assertTrue(form.fields['yandex_markup_from_wholesale'].disabled)
            result=update_product_card(actor=worker,product_kind=kind,product_id=product.pk,data={
                'version':product_version(product),'avito_price':'100', 'avito_markup_from_wholesale':'0',
            })
            self.assertTrue(result.saved,result.form.errors)
            product.refresh_from_db()
            self.assertEqual(product.avito_markup_from_wholesale,D(0))
            self.assertEqual(product.yandex_markup_from_wholesale,D(189))
            result=update_product_card(actor=worker,product_kind=kind,product_id=product.pk,data={
                'version':product_version(product),'avito_price':'100', 'avito_markup_from_wholesale':'',
            })
            self.assertTrue(result.saved,result.form.errors)
            product.refresh_from_db()
            self.assertIsNone(product.avito_markup_from_wholesale)
            result=update_product_card(actor=worker,product_kind=kind,product_id=product.pk,data={
                'version':product_version(product),'yandex_markup_from_wholesale':'1',
            })
            self.assertFalse(result.saved)

    def test_admin_permissions_and_card_markup_next_to_price(self):
        worker=User.objects.create_user('price-readonly')
        request=RequestFactory().get('/'); request.user=worker
        for product in (self.cd,self.tech):
            model_admin=admin.site._registry[type(product)]
            readonly=model_admin.get_readonly_fields(request,product)
            for field in MARKUP_FIELDS:self.assertIn(field,readonly)
        self.client.force_login(self.actor)
        response=self.client.get(reverse('nomenclature:cd_detail',args=[self.cd.pk]))
        self.assertContains(response,'name="avito_markup_from_wholesale"')
        self.assertContains(response,'name="yandex_markup_from_wholesale"')
        self.assertContains(response,'data-markup-for="avito_price"')
        fields=[f.name for section in response.context['form_sections'] if section['title']=='Коммерческая информация' for f in section['fields']]
        self.assertEqual(fields.index('avito_markup_from_wholesale'),fields.index('avito_price')+1)
        self.assertEqual(fields.index('yandex_markup_from_wholesale'),fields.index('yandex_market_price')+1)
