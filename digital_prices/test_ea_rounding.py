"""Ранее загруженный EA Play и предварительная цена используют тот же шаг 50 ₽."""
from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase
from .services import effective_rule, product_price
from .models import Product
from .catalog import product_data
from .public import product_row


class EaRoundingTests(SimpleTestCase):
    def product(self, **values):
        return Product(pk=1, source_type='ps', source_name='Ea Play · 1 мес.', attributes={},
            purchase_cost=Decimal('399'), markup=Decimal('750'), currency='RUB', rule='other', **values)

    def test_existing_ea_row_uses_fifty_even_before_next_import(self):
        row = self.product()
        self.assertEqual(effective_rule(row), Product.Rule.PS_PLUS)
        self.assertEqual(product_price(row), Decimal('1150'))
        self.assertEqual(product_row(row).price, '1 150 ₽')
        # Само отображение не переписывает сохранённые настройки.
        self.assertEqual(row.rule, Product.Rule.OTHER)

    def test_catalog_preview_uses_same_rule_as_png(self):
        row = self.product()
        data = product_data(row, SimpleNamespace(has_perm=lambda permission: True))
        self.assertEqual(data['rule'], Product.Rule.PS_PLUS)
        self.assertEqual(data['price'], '1 150 ₽')

    def test_other_products_keep_their_rule_and_empty_markup_stays_unknown(self):
        row = self.product()
        row.source_name, row.source_type = 'Услуга', 'cprod'
        self.assertEqual(product_price(row), Decimal('1150'))
        row.purchase_cost = Decimal('401')
        self.assertEqual(product_price(row), Decimal('1160'))
        row.source_name, row.source_type = 'Ea Play · 1 мес.', 'ps'
        self.assertEqual(product_price(row), Decimal('1200'))
        row.markup = None
        self.assertIsNone(product_price(row))
