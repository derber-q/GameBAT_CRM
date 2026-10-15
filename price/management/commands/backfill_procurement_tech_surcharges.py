from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from price.services import backfill_procurement_tech_surcharges


class Command(BaseCommand):
    help = "Применить ставки Tech к старым строкам закупочного прайса. Без --apply только предпросмотр."

    def add_arguments(self, parser):
        parser.add_argument("--price-list", type=int, required=True, help="ID закупочного прайса")
        parser.add_argument("--actor", type=int, required=True, help="ID сотрудника с правом изменения наценки")
        parser.add_argument("--apply", action="store_true", help="Записать исправления после резервного копирования БД")

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options["actor"], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("Активный сотрудник не найден.") from exc
        try:
            changes = backfill_procurement_tech_surcharges(
                actor=actor, price_list_id=options["price_list"], apply=options["apply"],
            )
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        changed_prices = sum(row["old_postpayment"] != row["new_postpayment"] for row in changes)
        action = "Исправлено" if options["apply"] else "Будет исправлено"
        self.stdout.write(f"{action} строк Tech: {len(changes)}. Изменение цены постоплаты: {changed_prices}.")
        if not options["apply"]:
            self.stdout.write("Предпросмотр: данные не изменены. Для записи используйте --apply после резервного копирования.")
