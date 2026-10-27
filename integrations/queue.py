from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .models import AvitoProductProfile, AvitoSyncJob, IntegrationCredential


@transaction.atomic
def ensure_required_actions_refresh():
    """Одна общая задача ручной и автоматической проверки статусов каждые 15 минут."""
    if not IntegrationCredential.objects.filter(provider='avito').exclude(
        encrypted_client_id='').exclude(encrypted_client_secret='').exists():
        return
    now = timezone.now()
    job, created = AvitoSyncJob.objects.select_for_update().get_or_create(
        dedupe_key='required-actions-refresh', defaults={
            'job_type': AvitoSyncJob.JobType.STATUS_REFRESH, 'run_after': now + timedelta(minutes=15),
            'phase': 'Автоматическая проверка статусов Avito',
        })
    if not created and job.status in (AvitoSyncJob.Status.DONE, AvitoSyncJob.Status.ERROR):
        if now >= (job.finished_at or job.updated_at) + timedelta(minutes=15):
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after, job.attempts, job.last_error = now, 0, ''
            job.phase = 'Автоматическая проверка статусов Avito'
            job.started_at = job.finished_at = None
            job.save()
    return job


def enqueue_profile_sync(profile_id, *, delay_seconds=None):
    delay = settings.AVITO_SYNC_DEBOUNCE_SECONDS if delay_seconds is None else delay_seconds
    try:
        profile = AvitoProductProfile.objects.get(pk=profile_id)
        AvitoSyncJob.objects.update_or_create(
            dedupe_key=f"product:{profile_id}",
            defaults={
                "job_type": AvitoSyncJob.JobType.PRODUCT,
                "profile": profile,
                "status": AvitoSyncJob.Status.PENDING,
                "run_after": timezone.now() + timedelta(seconds=delay),
                "attempts": 0,
                "last_error": "",
            },
        )
        AvitoProductProfile.objects.filter(pk=profile_id).update(
            sync_status=AvitoProductProfile.SyncStatus.QUEUED
        )
    except (AvitoProductProfile.DoesNotExist, OperationalError, ProgrammingError):
        return


def enqueue_profile_sync_after_commit(profile_id, *, delay_seconds=None):
    # Не отправлять в Avito состояние операции, которая затем откатится.
    # Прямые SQL/QuerySet.update не вызывают сигналы и требуют отдельного решения.
    transaction.on_commit(lambda: enqueue_profile_sync(profile_id, delay_seconds=delay_seconds))


def enqueue_periodic(job_type, *, delay_seconds=0):
    key = "refresh" if job_type == AvitoSyncJob.JobType.REFRESH else "reconcile"
    job, _ = AvitoSyncJob.objects.update_or_create(
        dedupe_key=key,
        defaults={
            "job_type": job_type,
            "profile": None,
            "status": AvitoSyncJob.Status.PENDING,
            "run_after": timezone.now() + timedelta(seconds=delay_seconds),
            "attempts": 0,
            "last_error": "",
        },
    )
    return job
