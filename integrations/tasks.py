from datetime import timedelta
import logging
import time

from django.db import OperationalError, transaction
from django.utils import timezone

from .client import AvitoAPIError
from .manual_sync import reconcile_active_listings
from .models import AvitoSyncJob
from .services import reconcile_all, refresh_remote_listings, sync_profile


RETRY_DELAYS = (60, 180, 300, 300)
logger = logging.getLogger("gamebat.business")


def _reschedule_after_database_lock(job):
    """Keep a recoverable SQLite write collision from losing the sync run."""
    for retry_number in range(5):
        try:
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(seconds=5)
            job.last_error = "Локальная база данных была занята; синхронизация автоматически повторяется."
            if job.job_type == AvitoSyncJob.JobType.MANUAL:
                job.phase = "База данных занята — повторная попытка"
            job.save()
            return
        except OperationalError as save_exc:
            if "locked" not in str(save_exc).lower() or retry_number == 4:
                logger.exception(
                    "Не удалось вернуть задачу Avito в очередь после блокировки БД: job_id=%s",
                    job.pk,
                )
                return
            time.sleep(0.5)


def ensure_periodic_jobs():
    now = timezone.now()
    AvitoSyncJob.objects.filter(
        status=AvitoSyncJob.Status.RUNNING,
        updated_at__lt=now - timedelta(minutes=15),
    ).update(
        status=AvitoSyncJob.Status.PENDING,
        run_after=now,
        last_error="Обработчик прервался во время синхронизации; задача повторяется.",
    )
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
        due_jobs = AvitoSyncJob.objects.select_for_update().filter(
            status=AvitoSyncJob.Status.PENDING, run_after__lte=timezone.now()
        )
        job = due_jobs.filter(job_type=AvitoSyncJob.JobType.MANUAL).order_by("run_after", "id").first()
        if job is None:
            job = due_jobs.order_by("run_after", "id").first()
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
    if job.job_type == AvitoSyncJob.JobType.MANUAL:
        job.started_at = timezone.now()
        job.finished_at = None
        job.save(update_fields=("started_at", "finished_at", "updated_at"))
    try:
        if job.job_type == AvitoSyncJob.JobType.PRODUCT:
            if job.profile_id:
                sync_profile(job.profile_id, retry_number=job.attempts)
        elif job.job_type == AvitoSyncJob.JobType.RECONCILE:
            reconcile_all(job=job)
        elif job.job_type == AvitoSyncJob.JobType.REFRESH:
            refresh_remote_listings()
        elif job.job_type == AvitoSyncJob.JobType.MANUAL:
            result = reconcile_active_listings(job=job)
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            logger.warning(
                "База данных временно занята; задача Avito будет повторена: job_id=%s",
                job.pk,
            )
            _reschedule_after_database_lock(job)
        else:
            logger.exception("Ошибка базы данных в задаче Avito: job_id=%s", job.pk)
            job.status = AvitoSyncJob.Status.ERROR
            job.last_error = str(exc)[:1000]
            if job.job_type == AvitoSyncJob.JobType.MANUAL:
                job.phase = "Не удалось завершить синхронизацию"
                job.finished_at = timezone.now()
            job.save()
    except AvitoAPIError as exc:
        job.refresh_from_db()
        can_retry = exc.retryable and (
            job.job_type != AvitoSyncJob.JobType.MANUAL or job.attempts < len(RETRY_DELAYS)
        )
        if can_retry:
            delay = exc.retry_after or RETRY_DELAYS[min(job.attempts, len(RETRY_DELAYS) - 1)]
            job.attempts = min(job.attempts + 1, len(RETRY_DELAYS))
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(seconds=delay)
            job.last_error = str(exc)
            if job.job_type == AvitoSyncJob.JobType.MANUAL:
                job.phase = "Ошибка соединения — повторная попытка"
        else:
            job.status = AvitoSyncJob.Status.ERROR
            job.last_error = str(exc)
            if job.job_type == AvitoSyncJob.JobType.MANUAL:
                job.phase = "Не удалось завершить синхронизацию"
                job.finished_at = timezone.now()
        job.save()
    except Exception as exc:
        logger.exception("Ошибка задачи синхронизации Avito: job_id=%s", job.pk)
        job.status = AvitoSyncJob.Status.ERROR
        job.last_error = str(exc)[:1000]
        if job.job_type == AvitoSyncJob.JobType.MANUAL:
            job.phase = "Не удалось завершить синхронизацию"
            job.finished_at = timezone.now()
        job.save()
    else:
        job.attempts = 0
        job.last_error = ""
        if job.job_type == AvitoSyncJob.JobType.RECONCILE:
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(minutes=5)
        elif job.job_type == AvitoSyncJob.JobType.REFRESH:
            job.status = AvitoSyncJob.Status.PENDING
            job.run_after = timezone.now() + timedelta(minutes=60)
        elif job.job_type == AvitoSyncJob.JobType.MANUAL:
            job.status = AvitoSyncJob.Status.ERROR if result["failed"] else AvitoSyncJob.Status.DONE
            job.last_error = (
                f"Не удалось синхронизировать {result['failed']} из {result['total']} объявлений. "
                "Подробности указаны ниже; автоматическая сверка продолжит проверки."
                if result["failed"] else ""
            )
            job.finished_at = timezone.now()
        else:
            job.status = AvitoSyncJob.Status.DONE
        job.save()
    return True
