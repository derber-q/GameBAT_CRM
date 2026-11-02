"""Отдельный управляемый процесс; отсутствие настройки не мешает веб-серверу."""
import uuid
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from integrations.worker_heartbeat import monitored_worker
from integrations.worker_runtime import AlreadyRunning, graceful_shutdown
from telegram_bots.configuration import expected_status, TEST_MESSAGE
from telegram_bots.models import StaffBot
from telegram_bots.worker import run_polling


class Command(BaseCommand):
    help = 'Обслуживает только личный Telegram-бот сотрудников.'

    def add_arguments(self, parser):
        parser.add_argument('--worker-instance', type=uuid.UUID)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        if settings.GAMEBAT_ENV == 'local_test':
            self.stdout.write(TEST_MESSAGE)
            return
        if expected_status() != 'required':
            self.stdout.write('Бот сотрудников не настроен или отключён.')
            return
        instance = options['worker_instance'] or uuid.uuid4()
        try:
            with graceful_shutdown() as stop, monitored_worker(['telegram_staff'], instance):
                run_polling(StaffBot.objects.get(code='staff').pk, instance, stop, once=options['once'])
        except AlreadyRunning:
            self.stdout.write('Telegram-бот уже обслуживается; повторный запуск отменён.')
        except ValidationError:
            self.stderr.write('Настройки Telegram недоступны. Проверьте защищённый источник токена.')
