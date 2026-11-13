"""Одно чтение ожидающих событий без подтверждения offset и без вывода содержимого."""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from digital_sales.models import DigitalBot
from digital_sales.configuration import read_token
from digital_sales.worker import SupplierClient
from telegram_bots.client import TelegramError


class Command(BaseCommand):
    help = 'Показывает только chat ID и sender ID из ожидающих Telegram updates; бот должен быть выключен.'

    def add_arguments(self, parser):
        parser.add_argument('--sender', action='append', default=[], help='Необязательный username отправителя без @')

    def handle(self, *args, **options):
        bot = DigitalBot.objects.filter(pk=1).first()
        if bot and (bot.enabled or bot.lease_until and bot.lease_until > timezone.now()):
            raise CommandError('Сначала выключите цифровой бот и дождитесь освобождения аренды.')
        names = {value.lstrip('@').lower() for value in options['sender']}
        client = SupplierClient(read_token())
        try:
            if client.call('getWebhookInfo').get('url'):
                raise CommandError('У бота настроен webhook. Диагностика polling не запускается.')
            # Нет offset: эти события не подтверждаются и не теряются для будущего worker.
            updates = client.call('getUpdates', {'timeout': 0, 'limit': 100,
                                                'allowed_updates': ['message', 'edited_message']})
            seen = set()
            for update in updates if isinstance(updates, list) else []:
                if not isinstance(update, dict):
                    continue
                message = update.get('message') or update.get('edited_message')
                if not isinstance(message, dict):
                    continue
                chat, sender = message.get('chat'), message.get('from')
                if not isinstance(chat, dict) or not isinstance(sender, dict) or chat.get('type') not in ('group', 'supergroup'):
                    continue
                username = str(sender.get('username', ''))
                if names and username.lower() not in names:
                    continue
                item = (chat.get('id'), sender.get('id'), username)
                if item not in seen:
                    seen.add(item)
                    self.stdout.write(f'chat_id={item[0]} sender_id={item[1]} username=@{username}')
            if not seen:
                self.stdout.write('Подходящих ожидающих событий нет. Проверьте режимы Telegram и дождитесь нового сообщения поставщика.')
        except TelegramError as exc:
            raise CommandError('Telegram: ' + exc.category) from None
        finally:
            client.close()
