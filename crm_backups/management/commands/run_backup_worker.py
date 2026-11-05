"""Независимый исполнитель, не блокирующий мониторинг/печать при упаковке."""
import time
from django.core.management.base import BaseCommand
from django.db import connections, close_old_connections,connection
from django.utils import timezone
from core.external_policy import require_live_operation
from print_agent.__main__ import exclusive
from crm_backups.configuration import backup_root,sqlite_worker_lock
from crm_backups.models import BackupConfiguration
from crm_backups.jobs import schedule, claim_job, run_job, recover_interrupted, expire_delivered


class Command(BaseCommand):
    help = 'Отдельный исполнитель ежедневных зашифрованных копий.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, **options):
        require_live_operation('backup_worker')
        if connection.vendor!='sqlite':
            raise ValueError('PostgreSQL-исполнитель ещё не допущен к полной копии.')
        backup_root()
        with exclusive(sqlite_worker_lock(connection.settings_dict['NAME'])):
            from crm_backups.staging import expire
            expire(backup_root())
            recover_interrupted()
            while True:
                close_old_connections()
                try:
                    config = BackupConfiguration.objects.filter(pk=1).first()
                    if config:
                        config.last_worker_at = timezone.now()
                        config.save(update_fields=['last_worker_at'])
                        if config.enabled:
                            schedule()
                            job = claim_job()
                            if job: run_job(job)
                            expire_delivered()
                except Exception as exc:
                    self.stderr.write('Резервирование: ' + type(exc).__name__)
                finally:
                    connections.close_all()
                if options['once']: return
                time.sleep(15)
