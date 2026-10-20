import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections, OperationalError
from sales.market_fulfillment import process_print_jobs


class Command(BaseCommand):
    help = 'Печатает ярлыки на локальный принтер и завершает сборку заказов Яндекса.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                process_print_jobs()
            except OperationalError:
                pass
            if options['once']:
                return
            time.sleep(1)
