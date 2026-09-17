from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from .models import AvitoProductProfile, AvitoSyncJob


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
