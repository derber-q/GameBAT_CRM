"""Редактор прайса сначала показывает позиции, требующие заполнения наценки."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier

from .models import ProcurementPriceList, ProcurementPriceListItem


class ProcurementOrderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('procurement-ordering-owner')
        cls.price_list = ProcurementPriceList.objects.create(
            created_by=cls.user, exchange_rate_aed_rub=1,
        )
        supplier = Supplier.objects.create(name='Поставщик', letter='A')
        platform = Platform.objects.create(name='PS5')
        brand = Brand.objects.create(name='Sony')
        product_type = ProductType.objects.create(name='Игровая консоль')
        cls.items = {}
        for index, (kind, name, configured, effective) in enumerate((
            ('tech', 'A: техника заполнена', '10', '10'),
            ('tech', 'Z: нулевая', '0', '3.84'),
            ('cd', 'A: заполнена', '0.01', '1'),
            ('cd', 'B: старая нулевая', None, '0'),
            ('cd', 'C: старая отрицательная', None, '-1'),
            ('cd', 'D: старая положительная', None, '1'),
            ('cd', 'Y: отрицательная до округления', '-0.01', '0.01'),
            ('cd', 'Z: нулевая до округления', '0', '3.84'),
        ), 1):
            product_fields = {'platform': platform} if kind == 'cd' else {
                'brand': brand, 'product_type': product_type,
            }
            product = (CD if kind == 'cd' else Tech).objects.create(
                name=name, sku=f'ORDER-{index}', **product_fields,
            )
            cls.items[name] = ProcurementPriceListItem.objects.create(
                price_list=cls.price_list, product_kind=kind, **{kind: product},
                product_name_snapshot=name, article_snapshot=product.sku,
                selected_supplier=supplier, supplier_price_aed=100,
                exchange_rate_aed_rub=1, base_price_rub=100,
                original_markup_rub=None if configured is None else Decimal(configured),
                markup_rub=Decimal(effective), prepayment_price_rub=110,
                postpayment_price_rub=170,
            )

    def test_editor_prioritizes_nonpositive_configured_markup_across_product_kinds(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('price:procurement_detail', args=[self.price_list.pk]))
        self.assertEqual(response.status_code, 200)
        expected = [self.items[name].pk for name in (
            'Z: нулевая', 'B: старая нулевая', 'C: старая отрицательная',
            'Y: отрицательная до округления', 'Z: нулевая до округления',
            'A: техника заполнена', 'A: заполнена', 'D: старая положительная',
        )]
        self.assertEqual([item.pk for item in response.context['items']], expected)
        html = response.content.decode()
        positions = [html.index(f'data-item-id="{pk}"') for pk in expected]
        self.assertEqual(positions, sorted(positions))
