import time

from django.core.management.base import BaseCommand

from integrations.tasks import process_one_job


class Command(BaseCommand):
    help = "Запускает DB-backed worker и планировщик интеграций."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll", type=float, default=2.0)

    def handle(self, *args, **options):
        while True:
            processed = process_one_job()
            if options["once"]:
                break
            if not processed:
                time.sleep(max(0.2, options["poll"]))
