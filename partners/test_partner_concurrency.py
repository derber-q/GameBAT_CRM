"""Две параллельные продажи не могут зачесть один и тот же остаток долга."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
import uuid
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase
from accounts.models import User
from warehouse.models import Warehouse
from creditors.models import CreditorTransaction
from creditors.services import adjust_creditor_debt
from sales.models import Sale
from sales.services import create_sale
from sales.partner_payments import quote, SALT
from .models import Partner


class PartnerConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('concurrent-partners')
        self.warehouse = Warehouse.objects.create(name='Конкурентный склад')
        self.partner = Partner.objects.create(name='Партнёр')
        adjust_creditor_debt(actor=self.actor, creditor_id=self.partner.creditor_id,
            warehouse_id=self.warehouse.pk, money_source_type='offset', new_debt='-3000', comment='Исходный долг')

    def run_sale(self, key, *, settlement=True):
        connections.close_all()
        try:
            token = signing.dumps(quote(total=Decimal('10000'), received='8000', debt=Decimal('-3000'),
                partner_id=self.partner.pk, creation_key=key), salt=SALT) if settlement else ''
            result = create_sale(actor=User.objects.get(pk=self.actor.pk), warehouse_id=self.warehouse.pk,
                price_type='wholesale', sale_type='wholesale', payment_method='bank_account',
                partner_id=self.partner.pk, creation_key=key, note='Конкурентный расчёт',
                cash_received_amount='8000' if settlement else None, settlement_confirmation=token,
                lines=[{'product_type': 'custom', 'name': 'Товар', 'quantity': 1, 'unit_price': '10000', 'unit_cost': '6000'}])
            return result.pk
        except ValidationError:
            return None
        finally:
            connections.close_all()

    def test_only_one_offset_can_consume_available_debt(self):
        barrier = Barrier(2)
        def simultaneous(key):
            barrier.wait(timeout=15)
            return self.run_sale(key)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(simultaneous, [uuid.uuid4(), uuid.uuid4()]))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.partner.creditor.refresh_from_db()
        self.assertEqual(self.partner.creditor.current_debt, -1000)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(CreditorTransaction.objects.filter(kind='offset').count(), 1)

    def test_duplicate_create_key_produces_one_sale(self):
        key = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.run_sale(key, settlement=False), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Sale.objects.count(), 1)
