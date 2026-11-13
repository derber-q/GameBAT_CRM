import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from sales.services import cancel_sale, mark_sale_paid, create_sale
from sales.statistics_service import build_sales_statistics_report as build_report
from .models import Buyer, Supplier, BalanceMovement, DigitalOrder
from . import services


class FinanceTests(TestCase):
    def setUp(self):
        from catalog.models import SystemProduct
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        self.user = get_user_model().objects.create_superuser(username='digital-test', password='test')
        self.buyer = Buyer.objects.create(name='Синтетический покупатель')
        self.supplier = Supplier.objects.create(name='Тестовый поставщик')
        services.move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='10000', kind='opening', reason='Тест')
        services.move_balance(actor=self.user, supplier_id=self.supplier.pk, amount='12521', kind='opening', reason='Тест')

    def sale(self, **changes):
        data = dict(actor=self.user, supplier_id=self.supplier.pk, buyer_id=self.buyer.pk,
                    items=[{'name': 'Synthetic A', 'cost': '1000'}, {'name': 'Synthetic B', 'cost': '500'}],
                    price='2000', creation_key=uuid.uuid4())
        data.update(changes)
        return services.manual_sale(**data)

    def test_completion_and_cancellation_use_only_internal_journals(self):
        from cash.models import CashTransaction
        before = CashTransaction.objects.count()
        sale = self.sale()
        self.assertFalse(sale.is_completed)
        self.assertIsNone(sale.warehouse_id)
        self.assertEqual(self.buyer.balance, Decimal('10000'))
        completed = mark_sale_paid(actor=self.user, sale_id=sale.pk)
        self.assertTrue(completed.is_completed)
        self.assertEqual(self.buyer.balance, Decimal('8000'))
        self.assertEqual(self.supplier.balance, Decimal('11021'))
        self.assertEqual(CashTransaction.objects.count(), before)
        self.assertFalse(sale.cd_items.exists())
        self.assertFalse(sale.tech_items.exists())
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        self.assertEqual(self.buyer.balance, Decimal('8000'))
        self.assertTrue(cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена теста').cancelled)
        self.assertEqual(self.buyer.balance, Decimal('10000'))
        self.assertEqual(self.supplier.balance, Decimal('12521'))
        self.assertFalse(cancel_sale(actor=self.user, sale_id=sale.pk, comment='Повтор').cancelled)

    def test_completion_allows_negative_balances_and_cancellation_restores_them(self):
        sale = self.sale(price='10001', items=[{'name': 'Synthetic', 'cost': '13000'}])
        completed = services.complete_sale(actor=self.user, sale_id=sale.pk)
        self.assertTrue(completed.is_completed)
        self.assertEqual(self.buyer.balance, Decimal('-1'))
        self.assertEqual(self.supplier.balance, Decimal('-479'))
        services.complete_sale(actor=self.user, sale_id=sale.pk)
        self.assertEqual(BalanceMovement.objects.filter(sale=sale, kind='sale').count(), 2)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена')
        self.assertEqual(self.buyer.balance, Decimal('10000'))
        self.assertEqual(self.supplier.balance, Decimal('12521'))

    def test_two_sales_can_take_buyer_balance_below_zero(self):
        first, second = self.sale(price='7000'), self.sale(price='7000')
        services.complete_sale(actor=self.user, sale_id=first.pk)
        services.complete_sale(actor=self.user, sale_id=second.pk)
        self.assertEqual(self.buyer.balance, Decimal('-4000'))

    def test_negative_opening_and_adjustment_for_both_account_types(self):
        for model, field in [(Buyer, 'buyer_id'), (Supplier, 'supplier_id')]:
            with self.subTest(account=field):
                owner = model.objects.create(name='Начальный долг')
                services.move_balance(actor=self.user, **{field: owner.pk}, amount='-100',
                                      kind='opening', reason='Начальный долг')
                services.move_balance(actor=self.user, **{field: owner.pk}, amount='-50',
                                      kind='adjustment', reason='Корректировка долга')
                self.assertEqual(owner.balance, Decimal('-150'))
                services.move_balance(actor=self.user, **{field: owner.pk}, amount='25',
                                      kind='topup', reason='Частичное погашение')
                self.assertEqual(owner.balance, Decimal('-125'))
                with self.assertRaises(ValidationError):
                    services.move_balance(actor=self.user, **{field: owner.pk}, amount='-1',
                                          kind='topup', reason='Неверное пополнение')

    def test_allocation_has_exact_cent_and_zero_cost_support(self):
        for costs in [[Decimal('0')] * 3, [Decimal('2317'), Decimal('418'), Decimal('2923')]]:
            amounts = services.allocate_price(Decimal('7000.01'), costs)
            self.assertEqual(sum(amounts), Decimal('7000.01'))
            self.assertTrue(all(value == value.quantize(Decimal('.01')) for value in amounts))
        sale = self.sale()
        self.assertEqual(sum(sale.custom_items.values_list('line_total', flat=True)), sale.total_amount)

    def test_idempotency_keys_and_supplier_numbers(self):
        key = uuid.uuid4()
        first = self.sale(creation_key=key, numbers=['99'])
        self.assertEqual(self.sale(creation_key=key, numbers=['99']).pk, first.pk)
        with self.assertRaises(ValidationError):
            self.sale(numbers=['99'])
        with self.assertRaises(ValidationError):
            self.sale(creation_key=key, price='2100')

    def test_versioned_shared_draft_and_single_confirmation(self):
        order = DigitalOrder.objects.create(supplier=self.supplier, checklist_received=True, goods_received=True,
                    items=[{'name': 'Test', 'cost': '5'}], cost='5', state='ready')
        services.save_draft(actor=self.user, order_id=order.pk, revision=1, buyer_id=self.buyer.pk, price='20')
        with self.assertRaises(ValidationError):
            services.save_draft(actor=self.user, order_id=order.pk, revision=1, buyer_id=self.buyer.pk, price='30')
        sale = services.confirm_order(actor=self.user, order_id=order.pk, revision=2)
        self.assertEqual(services.confirm_order(actor=self.user, order_id=order.pk, revision=2).pk, sale.pk)

    def test_permissions_rechecked_and_regular_path_cannot_bypass(self):
        employee = get_user_model().objects.create_user(username='no-permission')
        sale = self.sale()
        with self.assertRaises(PermissionDenied):
            mark_sale_paid(actor=employee, sale_id=sale.pk)
        with self.assertRaises(PermissionDenied):
            cancel_sale(actor=employee, sale_id=sale.pk, comment='forged')
        with self.assertRaises(ValidationError):
            create_sale(actor=self.user, warehouse_id=None, price_type='retail', sale_type='digital',
                        payment_method='bank_card', lines=[])

    def test_ledger_immutable_and_repeated_topup_does_not_duplicate(self):
        key = uuid.uuid4()
        for _ in range(2):
            services.move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='10', kind='topup', reason='Тест', operation_key=key)
        self.assertEqual(self.buyer.balance, Decimal('10010'))
        movement = BalanceMovement.objects.get(operation_key=key)
        with self.assertRaises(ValidationError):
            movement.save()
        with self.assertRaises(ValidationError):
            self.sale(price='NaN')

    def test_statistics_revenue_profit_and_no_new_money(self):
        sale = self.sale()
        services.complete_sale(actor=self.user, sale_id=sale.pk)
        report = build_report({})
        self.assertEqual(report.totals.actual_revenue, Decimal('2000'))
        self.assertEqual(report.totals.cost, Decimal('1500'))
        self.assertEqual(report.totals.profit, Decimal('500'))
        self.assertEqual(report.totals.actual_money, Decimal('0'))
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Тест')
        self.assertEqual(build_report({}).totals.actual_revenue, Decimal('0'))

    def test_retail_card_completes_once_without_buyer_wallet_and_cancel_restores_supplier(self):
        from cash.models import CashTransaction
        before_cash, before_buyers = CashTransaction.objects.count(), Buyer.objects.count()
        sale = self.sale(buyer_id=None, is_retail=True)
        self.assertTrue(sale.is_completed)
        self.assertEqual(sale.cash_received_amount, Decimal('2000'))
        self.assertEqual(sale.partner_name_snapshot, 'Розничный покупатель')
        self.assertIsNone(sale.partner_id)
        self.assertEqual(self.buyer.balance, Decimal('10000'))
        self.assertEqual(self.supplier.balance, Decimal('11021'))
        services.complete_sale(actor=self.user, sale_id=sale.pk)
        self.assertEqual(BalanceMovement.objects.filter(sale=sale, kind='sale').count(), 1)
        self.assertFalse(BalanceMovement.objects.filter(sale=sale, buyer__isnull=False).exists())
        self.assertEqual(Buyer.objects.count(), before_buyers)
        self.assertEqual(CashTransaction.objects.count(), before_cash)
        report = build_report({})
        self.assertEqual(report.totals.actual_money, Decimal('2000'))
        self.assertEqual(report.totals.profit, Decimal('500'))
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена розницы')
        sale.refresh_from_db()
        self.assertEqual(sale.refunded_amount, Decimal('2000'))
        self.assertEqual(self.supplier.balance, Decimal('12521'))
        self.assertEqual(self.buyer.balance, Decimal('10000'))
        self.assertEqual(build_report({}).totals.actual_money, Decimal('0'))

    def test_retail_requires_completion_permissions_before_creating_sale(self):
        from django.contrib.auth.models import Permission
        employee = get_user_model().objects.create_user(username='creator-only')
        employee.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='digital_sales', codename='create_digital_sales'),
            *Permission.objects.filter(content_type__app_label='sales', codename='create_sale'))
        with self.assertRaises(PermissionDenied):
            self.sale(actor=employee, buyer_id=None, is_retail=True)
        self.assertFalse(DigitalOrder.objects.exists())

    def test_retail_and_wallet_selection_are_exclusive(self):
        with self.assertRaises(ValidationError):
            self.sale(is_retail=True)
        self.assertFalse(Sale.objects.exists())
