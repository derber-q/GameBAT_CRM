import time

from django.core.management.base import BaseCommand

from integrations.tasks import process_one_job
from integrations.google_tasks import process_one_google_sheets_job
from yandex_market.tasks import process_one_job as process_yandex_job


class Command(BaseCommand):
    help = "Запускает DB-backed worker и планировщик интеграций."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll", type=float, default=2.0)
        parser.add_argument("--service", choices=("all", "avito", "google", "yandex"), default="all",
                            help="Обрабатывать только выбранную интеграцию или все сервисы.")

    def handle(self, *args, **options):
        processors = {"avito": process_one_job, "google": process_one_google_sheets_job, "yandex": process_yandex_job}
        selected = tuple(processors.values()) if options["service"] == "all" else (processors[options["service"]],)
        while True:
            processed = False
            for processor in selected:
                processed = processor() or processed
            if options["once"]:
                break
            if not processed:
                time.sleep(max(0.2, options["poll"]))
