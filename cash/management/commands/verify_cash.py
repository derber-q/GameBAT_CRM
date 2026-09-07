from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from cash.models import CashRegister, CashTransaction


class Command(BaseCommand):
    help = "Диагностирует расхождения между балансом кассы и журналом операций."

    def handle(self, *args, **options):
        errors = []
        for register in CashRegister.objects.all():
            incoming = register.transactions.exclude(
                operation_type=CashTransaction.OperationType.COLLECTION
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            outgoing = register.transactions.filter(
                operation_type=CashTransaction.OperationType.COLLECTION
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            expected = incoming - outgoing
            if register.balance != expected:
                errors.append(
                    f"Касса #{register.pk}: balance={register.balance}, сумма журнала={expected}"
                )
        if errors:
            for error in errors:
                self.stderr.write(error)
            raise CommandError(f"Обнаружено расхождений: {len(errors)}")
        self.stdout.write(self.style.SUCCESS("Балансы касс согласованы с журналом операций."))
