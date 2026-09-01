from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from catalog.models import CD, Tech


class Command(BaseCommand):
    help = "Диагностирует расхождения агрегированного остатка реализации."

    def handle(self, *args, **options):
        errors = []
        for model, label in ((CD, "CD"), (Tech, "Tech")):
            for product in model.objects.annotate(stock_total=Sum("consignment_stocks__quantity")):
                actual = product.stock_total or 0
                if product.quantity_on_consignment != actual:
                    errors.append(
                        f"{label} #{product.pk}: quantity_on_consignment={product.quantity_on_consignment}, "
                        f"сумма площадок={actual}"
                    )
        if errors:
            for error in errors:
                self.stderr.write(error)
            raise CommandError(f"Обнаружено расхождений: {len(errors)}")
        self.stdout.write(self.style.SUCCESS("Остатки склада и реализации согласованы."))
