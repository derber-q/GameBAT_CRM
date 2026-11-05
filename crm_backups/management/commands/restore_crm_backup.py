"""Только новый каталог; не запускает сайт и не перезаписывает рабочую SQLite."""
import getpass
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from crm_backups.snapshot import restore_bundle
from core.external_policy import require_live_operation


class Command(BaseCommand):
    help='Проверяет GCM/manifest/БД и распаковывает архив в новый отдельный каталог.'
    def add_arguments(self,parser):
        parser.add_argument('archive',type=Path);parser.add_argument('destination',type=Path)
        parser.add_argument('--private-key',type=Path,required=True)
    def handle(self,**options):
        require_live_operation('restore_crm_backup')
        password=getpass.getpass('Пароль приватного ключа восстановления: ').encode()
        try:
            manifest=restore_bundle(options['archive'],options['destination'],options['private_key'].read_bytes(),password)
        except Exception as exc:raise CommandError('Восстановление не подтверждено: '+type(exc).__name__) from None
        self.stdout.write(f"Архив проверен, файлов: {len(manifest['files'])}. Отдельный каталог: {options['destination']}")
        self.stdout.write('Сайт/worker/миграции не запускались. Не подключайте копию к реальным интеграциям при пробном восстановлении.')
