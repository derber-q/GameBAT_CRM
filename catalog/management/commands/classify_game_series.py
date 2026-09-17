"""Первичная классификация исторической базы CD без сетевых запросов."""

import csv
import json
from collections import Counter
from datetime import datetime, timezone as utc_timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.game_series_classifier import classify_game_title
from catalog.models import CD, GameSeries, normalize_game_series_name


class Command(BaseCommand):
    help = "Показывает или применяет классификацию существующих CD по игровым сериям."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Сохранить серии и связи в БД")
        parser.add_argument("--dry-run", action="store_true", help="Только предварительный CSV, без изменения БД")
        parser.add_argument("--force", action="store_true", help="Изменить и уже назначенные вручную серии")
        parser.add_argument("--report-dir", type=Path, default=Path(settings.BASE_DIR) / "reports" / "game_series")

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Используйте только один режим: --apply или --dry-run.")
        if options["force"] and not options["apply"]:
            raise CommandError("--force допустим только вместе с --apply.")

        rows = []
        assignments = []
        existing = list(CD.objects.active().select_related("platform", "game_series").order_by("id"))
        initially_assigned = sum(bool(product.game_series_id) for product in existing)
        for product in existing:
            proposed, reason = classify_game_title(product.name)
            proposed = normalize_game_series_name(proposed)
            if not proposed:
                raise CommandError(f"Не удалось определить серию для CD #{product.pk}.")
            old = product.game_series.name if product.game_series_id else ""
            keep_existing = bool(product.game_series_id and not options["force"])
            target = old if keep_existing else proposed
            if not target:
                raise CommandError(f"Пустая серия для CD #{product.pk}.")
            rows.append({
                "cd_id": product.pk,
                "cd_name": product.name,
                "platform": product.platform.name,
                "old_game_series": old,
                "game_series": target,
                "classifier_suggestion": proposed,
                "classification_source": "manual_preserved" if keep_existing else reason,
            })
            if not keep_existing and (
                not product.game_series_id
                or product.game_series.normalized_name != target.casefold()
            ):
                assignments.append((product, target))

        report_dir = options["report_dir"].resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(utc_timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        mode = "applied" if options["apply"] else "preview"
        report_path = report_dir / f"cd_game_series_{mode}_{timestamp}.csv"
        with report_path.open("x", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else (
                "cd_id", "cd_name", "platform", "old_game_series", "game_series",
                "classifier_suggestion", "classification_source",
            ))
            writer.writeheader()
            writer.writerows(rows)

        created = 0
        if options["apply"]:
            with transaction.atomic():
                series_by_key = {
                    series.normalized_name: series for series in GameSeries.objects.all()
                }
                for _, name in assignments:
                    key = name.casefold()
                    if key not in series_by_key:
                        series_by_key[key] = GameSeries.objects.create(name=name)
                        created += 1
                for product, name in assignments:
                    product.game_series = series_by_key[name.casefold()]
                CD.objects.bulk_update([product for product, _ in assignments], ["game_series"])

        summary = {
            "cd_total": len(existing),
            "series_created": created,
            "series_proposed": len({row["game_series"].casefold() for row in rows}),
            "cd_assigned": len(assignments) if options["apply"] else 0,
            "cd_already_assigned": initially_assigned,
            "manual_conflicts_preserved": sum(
                row["classification_source"] == "manual_preserved"
                and row["old_game_series"].casefold() != row["classifier_suggestion"].casefold()
                for row in rows
            ),
            "cd_without_series": CD.objects.active().filter(game_series__isnull=True).count(),
            "cd_projected_without_series": sum(not row["game_series"] for row in rows),
            "classification_sources": dict(Counter(row["classification_source"] for row in rows)),
            "report": str(report_path),
        }
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        if options["apply"] and summary["cd_without_series"]:
            raise CommandError("После классификации остались CD без серии; проверьте отчёт.")
