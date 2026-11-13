"""Явная локальная установка токена; не применяет миграции и не включает получателя."""
import os
import tempfile
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from core.external_policy import require_live_operation
from telegram_bots.configuration import validate_token
from wholesale_bot.configuration import token_path


class Command(BaseCommand):
    help = 'Без вывода токена копирует его из указанного защищённого файла. Бот остаётся выключенным.'

    def add_arguments(self, parser):
        parser.add_argument('--token-source', type=Path, required=True)

    def handle(self, *args, **options):
        require_live_operation('wholesale_token_setup')
        path = token_path()
        if path.exists() or path.is_symlink():
            raise CommandError('Файл токена уже существует; автоматическая перезапись запрещена.')
        try:
            source = options['token_source']
            if source.stat().st_size > 4096:
                raise ValueError()
            import re
            candidates = re.findall(r'[0-9]{5,20}:[A-Za-z0-9_-]{30,100}', source.read_text('utf-8-sig'))
            if len(candidates) != 1:
                raise ValueError()
            value = validate_token(candidates[0])
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(value)
        except Exception:
            raise CommandError('Не удалось установить токен. Проверьте источник и права; содержимое не выводится.') from None
        self.stdout.write('Токен сохранён локально. Бот не включён, сеть не использовалась.')
