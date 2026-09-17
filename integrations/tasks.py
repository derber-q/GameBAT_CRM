from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .client import AvitoAPIError
from .models import AvitoSyncJob
from .services import reconcile_all, refresh_remote_listings, sync_profile


RETRY_DELAYS = (60, 300, 900, 3600)


def ensure_periodic_jobs():
    now = timezone.now()
    AvitoSyncJob.objects.get_or_create(
        dedupe_key="reconcile",
        defaults={"job_type": AvitoSyncJob.JobType.RECONCILE, "run_after": now},
    )
    AvitoSyncJob.objects.get_or_create(
        dedupe_key="refresh",
        defaults={"job_type": AvitoSyncJob.JobType.REFRESH, "run_after": now},
    )


def claim_next_job():
    with transaction.atomic():
        job = AvitoSyncJob.objects.select_for_update().filter(
            status=AvitoSyncJob.Status.PENDING, run_after__lte=timezone.now()
        ).order_by("run_after", "id").first()
        if not job:
            return None
        job.status = AvitoSyncJob.Status.RUNNING
        job.save(update_fields=("status", "updated_at"))
        return job


def process_one_job():
    ensure_periodic_jobs()
    job = claim_next_job()
    if not job:
        return False
    try:
        if job.job_type == AvitoSyncJob.JobType.PRODUCT:
            if job.profile_id:
                sync_profile(job.profile_id, retry_number=job.attempts)
        elif job.job_type == AvitoSyncJob.JobType.RECONCILE:
            reconcile_all()
        elif job.job_type == AvitoSyncJob.JobType.REFRESH:
            refresh_remote_listings()
    except AvitoAPIError as exc:
        job.refresh_from_db()
        if exc.retryable and job.attempts < len(RETRY_DELAYS):
            delay = exc.retry_after or RETRY_DELAYS[job.attempts]
            job.attempts += 1
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(seconds=delay)
            job.last_error = str(exc)
        else:
            job.status = AvitoSyncJob.Status.ERROR
            job.last_error = str(exc)
        job.save()
    except Exception as exc:
        job.status = AvitoSyncJob.Status.ERROR
        job.last_error = str(exc)[:1000]
        job.save()
        raise
    else:
        job.attempts = 0
        job.last_error = ""
        if job.job_type == AvitoSyncJob.JobType.RECONCILE:
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(minutes=5)
        elif job.job_type == AvitoSyncJob.JobType.REFRESH:
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(minutes=60)
        else:
            job.status = AvitoSyncJob.Status.DONE
        job.save()
    return True
