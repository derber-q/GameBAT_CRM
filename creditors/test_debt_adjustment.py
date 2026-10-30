"""Итоговая сумма и относительное изменение через прежний денежный журнал."""
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from partners.models import Partner
from warehouse.models import Warehouse
from .forms import DebtAdjustmentForm
from .models import Creditor, CreditorTransaction
from .services import adjust_creditor_debt


class RelativeDebtAdjustmentTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('debt-adjustment')
        self.warehouse = Warehouse.objects.create(name='Склад изменения долга')
        self.creditor = Partner.objects.create(name='Партнёр').creditor
        self.register, self.safe = self.warehouse.cash_register, self.warehouse.safe
        for storage in (self.register, self.safe):
            storage.balance = Decimal('2000')
            storage.save(update_fields=['balance'])
        self.client.force_login(self.actor)
        self.url = reverse('creditors:debt', args=[self.creditor.pk])

    def adjust(self, **amount):
        return adjust_creditor_debt(actor=self.actor, creditor_id=self.creditor.pk,
            warehouse_id=self.warehouse.pk, money_source_type='cash', **amount)

    def test_relative_operations_keep_cash_safe_and_immutable_snapshots(self):
        first = self.adjust(debt_delta=Decimal('1000.25'))
        second = adjust_creditor_debt(actor=self.actor, creditor_id=self.creditor.pk,
            warehouse_id=self.warehouse.pk, money_source_type='safe', debt_delta=Decimal('-200.10'))
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('800.15'))
        self.assertEqual((self.register.balance, self.safe.balance), (Decimal('999.75'), Decimal('2200.10')))
        self.assertEqual((first.old_debt, first.new_debt, first.delta, first.amount),
            (Decimal('0'), Decimal('1000.25'), Decimal('1000.25'), Decimal('1000.25')))
        self.assertEqual((second.old_debt, second.new_debt, second.delta, second.amount),
            (Decimal('1000.25'), Decimal('800.15'), Decimal('-200.10'), Decimal('200.10')))
        self.assertEqual(second.cash_transaction.operation_type, CashTransaction.OperationType.CREDITOR_REPAYMENT)

    def test_relative_post_uses_latest_balance_and_ignores_browser_total(self):
        self.adjust(new_debt='100')
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.adjust(debt_delta='50')
        response = self.client.post(self.url, {'warehouse': self.warehouse.pk, 'money_source_type': 'cash',
            'amount_mode': 'change', 'change_direction': '+', 'change_amount': '25,15', 'new_debt': '125.15'})
        self.assertEqual(response.status_code, 302)
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('175.15'))
        last = self.creditor.transactions.first()
        self.assertEqual((last.old_debt, last.delta), (Decimal('150'), Decimal('25.15')))

    def test_partner_balance_can_cross_zero_in_both_directions(self):
        self.adjust(debt_delta='-100.01')
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('-100.01'))
        self.adjust(debt_delta='100.02')
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('0.01'))

    def test_legacy_account_still_cannot_become_negative(self):
        legacy = Creditor.objects.create(name='Без партнёра')
        with self.assertRaises(ValidationError):
            adjust_creditor_debt(actor=self.actor, creditor_id=legacy.pk, warehouse_id=self.warehouse.pk,
                money_source_type='cash', debt_delta='-1')
        self.assertFalse(CreditorTransaction.objects.exists())
        self.register.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal('2000'))

    def test_invalid_relative_requests_do_not_touch_money_or_journal(self):
        payload = {'warehouse': self.warehouse.pk, 'money_source_type': 'cash', 'amount_mode': 'change',
            'change_direction': '+', 'change_amount': '1'}
        for changes in ({'change_amount': ''}, {'change_amount': '-1'}, {'change_amount': '0'},
            {'change_amount': '0.001'}, {'change_direction': ''}, {'change_direction': 'invalid'},
            {'amount_mode': 'invalid'}, {'change_amount': 'NaN'}, {'change_amount': '2001'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post(self.url, {**payload, **changes}).status_code, 200)
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, self.register.balance), (Decimal('0'), Decimal('2000')))
        self.assertFalse(CreditorTransaction.objects.exists())
        self.assertFalse(CashTransaction.objects.exists())

    def test_relative_failure_rolls_back_money_and_debt(self):
        with patch('creditors.services.CreditorTransaction.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                self.adjust(debt_delta='100')
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, self.register.balance), (Decimal('0'), Decimal('2000')))
        self.assertFalse(CashTransaction.objects.exists())

    def test_database_still_rejects_a_one_kopeck_journal_mismatch(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CreditorTransaction.objects.create(creditor=self.creditor, actor=self.actor, warehouse=self.warehouse,
                money_source_type='offset', old_debt=Decimal('1000.25'), new_debt=Decimal('800.15'),
                delta=Decimal('-200.09'), amount=Decimal('200.09'))
        self.assertFalse(CreditorTransaction.objects.exists())

    def test_service_requires_exactly_one_amount_and_keeps_permissions(self):
        for amount in ({}, {'new_debt': '100', 'debt_delta': '100'}, {'debt_delta': '0'},
            {'debt_delta': 'Infinity'}, {'debt_delta': '1000000000000000000'}):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.adjust(**amount)
        employee = User.objects.create_user('no-debt-permission')
        with self.assertRaises(PermissionDenied):
            adjust_creditor_debt(actor=employee, creditor_id=self.creditor.pk, warehouse_id=self.warehouse.pk,
                money_source_type='cash', debt_delta='100')
        self.client.force_login(employee)
        self.assertEqual(self.client.post(self.url, {'amount_mode': 'change', 'change_amount': '100'}).status_code, 403)

    def test_old_total_post_and_total_form_validation_are_preserved(self):
        response = self.client.post(self.url, {'warehouse': self.warehouse.pk,
            'money_source_type': 'cash', 'new_debt': '150,25'})
        self.assertEqual(response.status_code, 302)
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('150.25'))
        form = DebtAdjustmentForm({'warehouse': self.warehouse.pk, 'money_source_type': 'cash', 'amount_mode': 'total'})
        self.assertFalse(form.is_valid())
        self.assertIn('new_debt', form.errors)

    def test_relative_offset_preserves_cash_and_requires_comment(self):
        for comment, expected_status in [('', 200), ('Коррекция взаиморасчётов', 302)]:
            response = self.client.post(self.url, {'warehouse': self.warehouse.pk, 'money_source_type': 'offset',
                'amount_mode': 'change', 'change_direction': '-', 'change_amount': '25.50', 'comment': comment})
            self.assertEqual(response.status_code, expected_status)
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, self.register.balance), (Decimal('-25.50'), Decimal('2000')))
        self.assertFalse(CashTransaction.objects.exists())
