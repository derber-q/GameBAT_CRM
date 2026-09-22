import csv
from dataclasses import asdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from integrations.client import AvitoAPIError
from integrations.verification import (
    MISMATCH,
    MISMATCH_FAILED,
    NOT_VERIFIABLE,
    verification_summary,
    verify_avito_connections,
)


class Command(BaseCommand):
    help = "Сверяет фактические остатки и цены связанных объявлений Avito с CRM."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Исправить подтверждённые расхождения штатной синхронизацией.")
        parser.add_argument("--output", help="Путь итогового CSV-отчёта.")

    def handle(self, *args, **options):
        try:
            rows = verify_avito_connections(fix=options["fix"])
        except AvitoAPIError as exc:
            raise CommandError(str(exc)) from exc
        output = Path(options["output"]) if options["output"] else Path(
            "reports/avito_verification"
        ) / f"avito_sync_{timezone.now():%Y%m%d_%H%M%S}.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "avito_id", "product_type", "product_id", "name", "expected_stock",
            "remote_stock", "stock_status", "expected_price", "remote_price",
            "price_status", "sync_action", "final_result",
        ]
        with output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: asdict(row)[key] for key in fieldnames})
        summary = verification_summary(rows)
        labels = (
            ("total", "Всего связанных объявлений"),
            ("stock_initial_match", "Остаток совпадал изначально"),
            ("stock_fixed", "Остаток исправлен"),
            ("stock_failed", "Остаток не удалось исправить"),
            ("price_initial_match", "Цена совпадала изначально"),
            ("price_fixed", "Цена исправлена"),
            ("price_failed", "Цену не удалось исправить"),
            ("not_verifiable", "Не удалось полностью проверить через API"),
        )
        for key, label in labels:
            self.stdout.write(f"{label}: {summary[key]}")
        unresolved = [
            row for row in rows
            if row.final_result in {MISMATCH, MISMATCH_FAILED, NOT_VERIFIABLE}
        ]
        if unresolved:
            self.stdout.write("Неподтверждённые объявления: " + ", ".join(
                f"#{row.avito_id} ({row.final_result})" for row in unresolved
            ))
        self.stdout.write(f"Отчёт: {output.resolve()}")
