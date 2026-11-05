"""Долговечная очередь: HTTP только ставит заявку, снимок выполняет отдельный worker."""
from datetime import datetime, timedelta
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction, connection
from django.utils import timezone
from core.db_retry import retry_database_lock
from core.external_policy import require_live_operation
from .crypto import public_id
from .models import BackupConfiguration, BackupJob, BackupEvent, ACTIVE


def audit(action, *, actor=None, job=None, **details):
    BackupEvent.objects.create(action=action, actor=actor, job=job, details=details)


def locked_config():
    config, _ = BackupConfiguration.objects.get_or_create(pk=1)
    # Первый SQL-запрос записи сериализует операции и в SQLite. Одного
    # select_for_update недостаточно для конкурентных регистраций/заявок.
    config.save(update_fields=['enabled'])
    return BackupConfiguration.objects.select_for_update().get(pk=1)


@retry_database_lock
@transaction.atomic
def request_job(request_id, *, actor=None, kind='manual', scheduled_for=None):
    require_live_operation('backup_request')
    config = locked_config()
    if not config.enabled or not config.recovery_key_saved:
        raise ValidationError('Резервирование выключено или сохранение ключа владельцем не подтверждено.')
    public_id(config.public_key.encode())
    previous = BackupJob.objects.filter(request_id=request_id).first()
    if previous: return previous
    active = BackupJob.objects.filter(state__in=ACTIVE).first()
    if active: return active
    if BackupJob.objects.filter(state__in=['ready', 'downloading']).count() >= config.max_pending:
        raise ValidationError('Достигнут лимит архивов, ожидающих устройство.')
    job = BackupJob.objects.create(request_id=request_id, actor=actor, kind=kind, scheduled_for=scheduled_for,
        metadata={'environment_id':str(config.environment_id)})
    audit('backup_requested', actor=actor, job=job, kind=kind)
    return job


@retry_database_lock
@transaction.atomic
def schedule(now=None):
    require_live_operation('backup_schedule')
    config = locked_config()
    now = (now or timezone.now()).astimezone(ZoneInfo(config.timezone))
    if not config.enabled or now.time().replace(tzinfo=None) < config.schedule_time or config.last_schedule_day == now.date():
        return None
    # Идущая ручная операция не подменяет ежедневную. Ждём её окончания,
    # прежде чем назначить фактический ежедневный снимок этого дня.
    if active:=BackupJob.objects.filter(state__in=ACTIVE).first():return active
    if config.last_schedule_day and config.last_schedule_day < now.date() - timedelta(days=1):
        missed = BackupJob.objects.create(request_id=uuid.uuid4(), active_slot=None, kind='missed', state='skipped',
            scheduled_for=config.last_schedule_day + timedelta(days=1), finished_at=timezone.now(),
            metadata={'missed_through': str(now.date()-timedelta(days=1))})
        audit('schedule_missed', job=missed)
    request_id = uuid.uuid5(config.environment_id, 'daily:' + now.date().isoformat())
    if BackupJob.objects.filter(state__in=['ready','downloading']).count()>=config.max_pending:
        job=BackupJob.objects.create(request_id=request_id,active_slot=None,kind='daily',state='skipped',
            scheduled_for=now.date(),finished_at=timezone.now(),error='pending_queue_full')
        audit('schedule_skipped_capacity',job=job)
    else:
        job = request_job(request_id, kind='daily', scheduled_for=now.date())
    config.last_schedule_day = now.date()
    config.save(update_fields=['last_schedule_day'])
    return job


@retry_database_lock
@transaction.atomic
def claim_job():
    locked_config()
    job = BackupJob.objects.select_for_update().filter(state='queued').order_by('created_at').first()
    if job:
        job.state = 'snapshot'; job.started_at = timezone.now()
        job.save(update_fields=['state', 'started_at'])
    return job


def archive_path(job):
    from .configuration import backup_root
    return backup_root() / (str(uuid.UUID(str(job.pk))) + '.backup')


def run_job(job):
    from .configuration import columns, recovery_secrets, version_metadata,backup_root
    from .snapshot import create_bundle
    from .client_apps import artifact_root
    require_live_operation('backup_snapshot')
    from .window import publish, marker_path
    try:
        config = BackupConfiguration.objects.get(pk=1)
        if not config.enabled or not config.recovery_key_saved:
            raise ValidationError('Резервирование отключено.')
        if connection.vendor != 'sqlite':
            raise ValidationError('PostgreSQL требует отдельно проверенного адаптера и согласованного окна.')
        files, encrypted = columns()
        meta = version_metadata()
        meta['environment_id'] = str(config.environment_id)
        backup_root()
        publish(job.pk, 'staging')
        result = create_bundle(database=Path(connection.settings_dict['NAME']), media=Path(settings.MEDIA_ROOT),
            secrets_loader=recovery_secrets, metadata=meta, public_key=config.public_key.encode(),
            destination=archive_path(job), file_columns=files, encrypted_columns=encrypted,
            window_seconds=min(15, getattr(settings, 'CRM_BACKUP_WINDOW_SECONDS', 15)),
            phase=lambda value: publish(job.pk, value),extra_roots={'client_applications':artifact_root()})
        job.state, job.active_slot = 'ready', None
        job.sha256, job.size, job.key_id = result['sha256'], result['size'], result['key_id']
        job.metadata = {**meta, 'snapshot_at': result['snapshot_at'], 'format': 1,
                        'write_window_seconds':result['manifest']['write_window_seconds'],
                        'integrity_check': 'ok', 'foreign_key_errors': 0}
        job.error = ''
    except Exception as exc:
        # Только категория; пути, содержимое БД и ключи не попадают в журнал.
        job.state, job.active_slot = 'error', None
        job.error = type(exc).__name__[:80]
    finally:
        marker_path().unlink(missing_ok=True)
    job.finished_at = timezone.now()
    job.save()
    audit('backup_' + job.state, job=job)


def recover_interrupted():
    for job in BackupJob.objects.filter(state__in=ACTIVE).exclude(state='queued'):
        job.state, job.active_slot, job.error = 'error', None, 'interrupted_review_required'
        job.finished_at = timezone.now(); job.save()
        audit('backup_interrupted', job=job)


def expire_delivered():
    """Удаляет только старые доставленные файлы из собственного UUID-хранилища."""
    from .snapshot import digest
    config = BackupConfiguration.objects.filter(pk=1).first()
    if not config: return
    cutoff = timezone.now() - timedelta(days=max(1, config.retention_days))
    for job in BackupJob.objects.filter(state='verified', downloaded_at__lt=cutoff):
        path = archive_path(job)
        if path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1 and digest(path) == job.sha256:
            path.unlink()
            job.state = 'expired'; job.save(update_fields=['state'])
            audit('backup_server_expired', job=job)
