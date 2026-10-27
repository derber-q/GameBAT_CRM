"""Денежные инварианты фактической доставки и копеечных групп единиц."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from core.allocation import allocate_amount
from .arrival_math import purchase_cost, unit_cohorts


class ArrivalMathTests(SimpleTestCase):
    def test_cross_conversion(self):
        self.assertEqual(purchase_cost('100', '3.66', '88.06'), Decimal('2406.01'))

    def test_category_tariffs_determine_shares(self):
        self.assertEqual(allocate_amount(Decimal('15000'), [2000, 3000, 5000]),
                         [Decimal('3000'), Decimal('4500'), Decimal('7500')])

    def test_reduction_keeps_full_actual_delivery(self):
        result = allocate_amount(Decimal('15000'), [1000, 3000, 5000])
        self.assertEqual(sum(result), Decimal('15000'))
        self.assertEqual(result, [Decimal('1666.67'), Decimal('5000'), Decimal('8333.33')])

    def test_largest_remainders_are_exact_and_deterministic(self):
        self.assertEqual(allocate_amount(Decimal('.02'), [1, 1, 1]), [Decimal('.01'), Decimal('.01'), Decimal('0')])
        self.assertEqual(allocate_amount(Decimal('1'), [0, 2, 0]), [Decimal('0'), Decimal('1'), Decimal('0')])

    def test_no_fake_weights_or_empty_composition(self):
        for amount, weights in ((Decimal('1'), [0, 0]), (Decimal('1'), []), (Decimal('-1'), [1]),
                                (Decimal('NaN'), [1]), (Decimal('1'), [-1, 2])):
            with self.subTest(amount=amount, weights=weights), self.assertRaises(ValidationError):
                allocate_amount(amount, weights)

    def test_unit_cohorts_preserve_exact_amount_without_zero_quantity(self):
        for amount, qty in ((Decimal('100.01'), 3), (Decimal('.01'), 7), (Decimal('0'), 2), (Decimal('101'), 1)):
            with self.subTest(amount=amount, qty=qty):
                rows = unit_cohorts(amount, qty)
                self.assertEqual(sum(count for count, cost in rows), qty)
                self.assertEqual(sum(count * cost for count, cost in rows), amount)
                self.assertTrue(all(count > 0 and cost >= 0 for count, cost in rows))
                self.assertLessEqual(len(rows), 2)
