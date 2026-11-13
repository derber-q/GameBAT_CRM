"""Явная локальная подготовка, без запуска polling, отправок и финансовых движений."""
import os
from pathlib import Path
import re
from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand, CommandError
from core.external_policy import require_live_operation
from digital_sales.crypto import key_path, cipher
from digital_sales.configuration import token_path
from telegram_bots.configuration import validate_token


def write_new(path, value):
    if path.exists() or path.is_symlink():
        raise CommandError('Файл уже существует. Автоматическая перезапись ключа/токена запрещена.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


class Command(BaseCommand):
    help = 'Готовит отдельный ключ шифрования и локальный токен. Секреты не выводятся.'

    def add_arguments(self, parser):
        parser.add_argument('--initialize-key', action='store_true')
        parser.add_argument('--token-source', type=Path)

    def handle(self, *args, **options):
        require_live_operation('configure_digital_secrets')
        if options['initialize_key']:
            write_new(key_path(), Fernet.generate_key())
            # Пробное шифрование/чтение не пишет секреты в БД.
            test = cipher()
            if test.decrypt(test.encrypt(b'digital-key-check')) != b'digital-key-check':
                raise CommandError('Ключ не прошёл проверку.')
            self.stdout.write('Ключ создан и проверен. Сохраните отдельную защищённую копию до использования.')
        if options['token_source']:
            try:
                text = options['token_source'].read_text(encoding='utf-8-sig')
                found = re.findall(r'(?<![A-Za-z0-9_])\d{5,20}:[A-Za-z0-9_-]{30,100}(?![A-Za-z0-9_-])', text)
                if len(found) != 1:
                    raise CommandError('В источнике должен быть ровно один токен.')
                token = validate_token(found[0])
                write_new(token_path(), token.encode('utf-8'))
            except OSError:
                raise CommandError('Источник токена недоступен.') from None
            self.stdout.write('Токен сохранён локально без вывода. Получатель не запускался.')
