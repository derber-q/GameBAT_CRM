import uuid
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from integrations.worker_heartbeat import monitored_worker
from integrations.worker_runtime import graceful_shutdown, AlreadyRunning
from wholesale_bot.worker import run_polling
from wholesale_bot.configuration import expected_status
from telegram_bots.recovery import run_autonomous


class Command(BaseCommand):
    help = 'Независимый оптовый бот покупателей; штатный supervisor, свой токен и offset.'

    def add_arguments(self, parser):
        parser.add_argument('--worker-instance', type=uuid.UUID)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        if expected_status() != 'required':
            self.stdout.write('Оптовый бот выключен или не настроен.')
            return
        try:
            with graceful_shutdown() as stop, monitored_worker(['telegram_opt'], options['worker_instance']) as health:
                run_autonomous(lambda: run_polling(stop, once=options['once'], health=health),
                    service='telegram_opt', stop=stop, expected=expected_status, health=health, once=options['once'])
        except AlreadyRunning:
            self.stdout.write('Оптовый бот уже обслуживается.')
        except ValidationError:
            self.stderr.write('Проверьте защищённую конфигурацию оптового бота.')
