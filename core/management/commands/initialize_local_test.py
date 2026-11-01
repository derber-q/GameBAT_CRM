"""Только синтетические пользователь/склад, без копирования рабочей базы."""
import json
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Создаёт учебную учётную запись в local_test; рабочий режим запрещён.'

    def handle(self, *args, **options):
        if settings.GAMEBAT_ENV != 'local_test':
            raise CommandError('Команда разрешена только в local_test.')
        path = settings.GAMEBAT_DATA_ROOT / 'secrets/test-admin.json'
        with transaction.atomic():
            User = get_user_model()
            if not User.objects.filter(username='test-admin').exists():
                password = secrets.token_urlsafe(24)
                User.objects.create_superuser(username='test-admin', password=password)
                with path.open('x', encoding='utf-8') as stream:
                    json.dump({'username':'test-admin','password':password}, stream)
            from warehouse.models import Warehouse
            Warehouse.objects.get_or_create(name='Учебный склад')
        self.stdout.write('Учебная учётная запись готова. Данные входа: secrets/test-admin.json внутри тестового каталога.')
