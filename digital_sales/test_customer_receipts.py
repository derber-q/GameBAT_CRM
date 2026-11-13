"""Публичные чеки: секретные поля не читаются, длинный состав не обрезается."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from django.test import SimpleTestCase
from django.utils import timezone
from .customer_receipts import receipt_parts, public_title


class CustomerReceiptTests(SimpleTestCase):
    def sale(self, titles):
        manager = Mock()
        manager.only.return_value.order_by.return_value = [
            SimpleNamespace(product_name_snapshot=title, quantity=1) for title in titles]
        return SimpleNamespace(pk=123, total_amount=Decimal('987.65'), custom_items=manager)

    def test_only_customer_fields_and_balance_are_formatted(self):
        sale = self.sale(['PlayStation Plus Extra 12 мес.', 'Xbox Game Pass'])
        texts = receipt_parts(sale=sale, balance=Decimal('-12.35'), at=timezone.now())
        self.assertEqual(len(texts), 1)
        self.assertIn('SALE-000123', texts[0])
        self.assertIn('PlayStation Plus Extra 12 мес. × 1', texts[0])
        self.assertIn('Xbox Game Pass × 1', texts[0])
        self.assertIn('Сумма продажи: 987,65 ₽', texts[0])
        self.assertIn('-12,35 ₽', texts[0])
        sale.custom_items.only.assert_called_once_with('product_name_snapshot', 'quantity')

    def test_titles_cannot_echo_supplier_details_or_costs(self):
        for title in ['PanYanStore: себестоимость 123.45', 'PAN-YAN-STORE товар 123.45',
                      'Поставщик: цена закупки 123.45', 'unit_cost_snapshot: 123.45',
                      '@PanYanStoreBot PS Plus', 'https://supplier.invalid/123.45',
                      'Login: private@example.invalid']:
            with self.subTest(title=title):
                text = '\n'.join(receipt_parts(sale=self.sale([title]), balance=Decimal('0'), at=timezone.now()))
                self.assertIn('Цифровой товар × 1', text)
                self.assertNotIn('123.45', text)
                self.assertNotIn('panyan', text.lower())
                self.assertNotIn('себестоимость', text.lower())

    def test_all_hundred_long_titles_fit_without_losing_positions(self):
        titles = [f'Позиция {number:03d} ' + '🎮' * 200 for number in range(100)]
        parts = receipt_parts(sale=self.sale(titles), balance=Decimal('0'), at=timezone.now())
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(text.encode('utf-16-le')) // 2 <= 4096 for text in parts))
        joined = '\n'.join(parts)
        for number in range(100):
            self.assertEqual(joined.count(f'Позиция {number:03d} '), 1)

    def test_control_characters_and_empty_title_are_safe(self):
        self.assertEqual(public_title('PS\x00 Plus\nExtra'), 'PS Plus Extra')
        self.assertEqual(public_title(''), 'Цифровой товар')
