"""План и безопасное однократное присвоение исторического статуса новинки."""
import json
import sqlite3
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from catalog.newness_backfill import apply_newness_backfill, build_newness_backfill, web_creation_evidence


class Command(BaseCommand):
    help = 'Проверяет происхождение карточек за календарный месяц; без --apply только отчёт.'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=int, required=True, help='ID пользователя, лично создавшего товары')
        parser.add_argument('--as-of', help='Дата внедрения ISO 8601 с часовым поясом; по умолчанию сейчас')
        parser.add_argument('--report', required=True, help='Путь JSON-отчёта, включая неопределённые карточки')
        parser.add_argument('--web-log-dir', help='Журналы сервера для дополнительной проверки цепочки HTTP-создания')
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--dry-run', action='store_true')
        mode.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not get_user_model().objects.filter(pk=options['user']).exists():
            raise CommandError('Указанный пользователь не найден.')
        as_of = parse_datetime(options['as_of']) if options['as_of'] else timezone.now()
        if not as_of or timezone.is_naive(as_of):
            raise CommandError('Укажите корректную дату внедрения с часовым поясом.')
        try:
            plan = build_newness_backfill(user_id=options['user'], as_of=as_of,
                                         web_evidence=web_creation_evidence(options['web_log_dir']))
            self.stdout.write('Период: ' + plan['since'] + ' — ' + plan['as_of'])
            self.stdout.write(json.dumps(plan['counts'], ensure_ascii=False))
            backup_path = None
            if options['apply'] and plan['counts'].get('eligible', 0):
                if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
                    raise CommandError('Для этой БД сначала настройте согласованное резервное копирование.')
                backup_dir = Path(settings.BASE_DIR) / 'backups'
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / ('before_product_newness_' + timezone.now().strftime('%Y%m%d_%H%M%S_%f') + '.sqlite3')
                db_path = Path(settings.DATABASES['default']['NAME'])
                with sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True) as source:
                    with sqlite3.connect(backup_path) as backup:
                        source.backup(backup)
                        if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                            raise CommandError('Резервная копия не прошла проверку целостности.')
            changed = apply_newness_backfill(plan) if options['apply'] else []
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        plan.update({'applied': bool(options['apply']), 'changed': changed, 'backup': str(backup_path) if backup_path else None})
        target = Path(options['report'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(plan, ensure_ascii=False, indent=2), 'utf-8')
        self.stdout.write(f'Изменено: {len(changed)}. Отчёт: {target}')
