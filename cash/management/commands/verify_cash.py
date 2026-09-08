from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from cash.models import CashRegister, CashTransaction, Safe


class Command(BaseCommand):
    help = "Диагностирует расхождения балансов касс и сейфов с единым журналом операций."

    def handle(self, *args, **options):
        errors = []
        for register in CashRegister.objects.all():
            incoming = register.transactions.filter(
                operation_type__in=(
                    CashTransaction.OperationType.DEPOSIT,
                    CashTransaction.OperationType.SALE_PAYMENT,
                    CashTransaction.OperationType.SAFE_TO_CASH,
                )
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            outgoing = register.transactions.filter(
                operation_type__in=(
                    CashTransaction.OperationType.COLLECTION,
                    CashTransaction.OperationType.CASH_TO_SAFE,
                )
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            expected = incoming - outgoing
            if register.balance != expected:
                errors.append(
                    f"Касса #{register.pk}: balance={register.balance}, сумма журнала={expected}"
                )
        for safe in Safe.objects.all():
            incoming = safe.transactions.filter(
                operation_type__in=(
                    CashTransaction.OperationType.SAFE_DEPOSIT,
                    CashTransaction.OperationType.CASH_TO_SAFE,
                )
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            outgoing = safe.transactions.filter(
                operation_type__in=(
                    CashTransaction.OperationType.SAFE_COLLECTION,
                    CashTransaction.OperationType.SAFE_TO_CASH,
                )
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            expected = incoming - outgoing
            if safe.balance != expected:
                errors.append(
                    f"Сейф #{safe.pk}: balance={safe.balance}, сумма журнала={expected}"
                )
        if errors:
            for error in errors:
                self.stderr.write(error)
            raise CommandError(f"Обнаружено расхождений: {len(errors)}")
        self.stdout.write(self.style.SUCCESS("Балансы касс и сейфов согласованы с журналом операций."))
