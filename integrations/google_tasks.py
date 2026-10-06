from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from .google_sheets import get_google_sheets_integration, sync_price_sheet
from .models import GoogleSheetsIntegration, GoogleSheetsSyncJob


RETRY_DELAYS_MINUTES = (1, 3, 10, 30)


def enqueue_google_sheets_sync(*, requested_by=None, manual=False):
    key = "manual" if manual else "periodic"
    job, created = GoogleSheetsSyncJob.objects.get_or_create(
        dedupe_key=key,
        defaults={"run_after": timezone.now(), "requested_by": requested_by},
    )
    if not created and job.status not in (GoogleSheetsSyncJob.Status.PENDING, GoogleSheetsSyncJob.Status.RUNNING):
        job.status = GoogleSheetsSyncJob.Status.PENDING
        job.run_after = timezone.now()
        job.attempts = 0
        job.last_error = ""
        job.requested_by = requested_by
        job.save()
    integration = get_google_sheets_integration()
    integration.status = GoogleSheetsIntegration.Status.QUEUED
    integration.save(update_fields=("status", "updated_at"))
    return job


def ensure_periodic_google_sheets_job():
    integration = get_google_sheets_integration()
    if not integration.enabled:
        return
    now = timezone.now()
    GoogleSheetsSyncJob.objects.filter(
        status=GoogleSheetsSyncJob.Status.RUNNING, updated_at__lt=now - timedelta(minutes=15),
    ).update(
        status=GoogleSheetsSyncJob.Status.PENDING, run_after=now,
        last_error="Обработчик прервался; задача будет повторена.",
    )
    job, _ = GoogleSheetsSyncJob.objects.get_or_create(
        dedupe_key="periodic", defaults={"run_after": now},
    )
    if job.status == GoogleSheetsSyncJob.Status.ERROR and job.run_after <= now:
        job.status = GoogleSheetsSyncJob.Status.PENDING
        job.attempts = 0
        job.started_at = None
        job.finished_at = None
        job.save(update_fields=(
            "status", "attempts", "started_at", "finished_at", "updated_at",
        ))


def process_one_google_sheets_job():
    ensure_periodic_google_sheets_job()
    with transaction.atomic():
        job = GoogleSheetsSyncJob.objects.select_for_update().filter(
            status=GoogleSheetsSyncJob.Status.PENDING, run_after__lte=timezone.now(),
        ).order_by("run_after", "id").first()
        if job is None:
            return False
        job.status = GoogleSheetsSyncJob.Status.RUNNING
        job.started_at = timezone.now()
        job.finished_at = None
        job.save(update_fields=("status", "started_at", "finished_at", "updated_at"))
    try:
        sync_price_sheet()
    except Exception as exc:
        job.attempts += 1
        job.last_error = str(exc)[:2000]
        if job.attempts <= len(RETRY_DELAYS_MINUTES):
            job.status = GoogleSheetsSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(minutes=RETRY_DELAYS_MINUTES[job.attempts - 1])
        else:
            job.status = GoogleSheetsSyncJob.Status.ERROR
            job.run_after = timezone.now() + timedelta(minutes=30)
            job.finished_at = timezone.now()
        job.save()
    else:
        job.attempts = 0
        job.last_error = ""
        job.finished_at = timezone.now()
        if job.dedupe_key == "periodic":
            job.status = GoogleSheetsSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(minutes=10)
        else:
            job.status = GoogleSheetsSyncJob.Status.DONE
        job.save()
    return True
