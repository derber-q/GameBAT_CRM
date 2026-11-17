import uuid
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError, ImproperlyConfigured
from integrations.worker_heartbeat import monitored_worker
from integrations.worker_runtime import AlreadyRunning, graceful_shutdown
from digital_sales.configuration import expected_status
from digital_sales.worker import run_polling
from telegram_bots.recovery import run_autonomous


class Command(BaseCommand):
    help = 'Пассивно получает события цифрового поставщика; не отправляет сообщения в его чат.'

    def add_arguments(self, parser):
        parser.add_argument('--worker-instance', type=uuid.UUID)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        if expected_status() != 'required':
            self.stdout.write('Цифровой бот отключён или не настроен.')
            return
        owner = options['worker_instance'] or uuid.uuid4()
        try:
            with graceful_shutdown() as stop, monitored_worker(['telegram_digital'], owner) as health:
                run_autonomous(lambda: run_polling(owner, stop, once=options['once'], health=health),
                    service='telegram_digital', stop=stop, expected=expected_status, health=health, once=options['once'])
        except AlreadyRunning:
            self.stdout.write('Цифровой бот уже обслуживается.')
        except (ValidationError, ImproperlyConfigured):
            self.stderr.write('Ошибка защищённой конфигурации цифрового бота. Проверьте ключ и источник токена.')
