"""Один исполнитель XLSX, отдельный от polling. Неопределённая отправка не повторяется."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from .access import check_access, BotDenied
from .client import TelegramError
from .documents import wholesale_document
from .models import StaffBotJob, StaffBotAccess


@retry_database_lock
@transaction.atomic
def claim_job(bot_id):
    job = StaffBotJob.objects.select_for_update().filter(bot_id=bot_id, state='queued').first()
    if job:
        job.state, job.started_at = 'generating', timezone.now()
        job.save(update_fields=['state', 'started_at'])
    return job


def finish_job(job, state, category='', message_id=None):
    job.state, job.error_category = state, category
    job.finished_at, job.telegram_message_id = timezone.now(), message_id
    job.save(update_fields=['state', 'error_category', 'finished_at', 'telegram_message_id'])


def run_job(job, client, *, owner=None):
    if job.state != 'generating':
        return
    dispatch_started = False
    try:
        access = StaffBotAccess.objects.get(pk=job.access_id)
        check_access(access)
        if access.telegram_user_id != job.chat_id:
            raise BotDenied()
        filename, data = wholesale_document(access, job.warehouse_id)
        # Проверяем свежую привязку и permissions непосредственно перед отправкой.
        access.refresh_from_db()
        check_access(access)
        if access.telegram_user_id != job.chat_id:
            raise BotDenied()
        if owner is not None:
            bot = access.bot
            bot.refresh_from_db()
            if bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now():
                raise BotDenied()
        job.state = 'sending'
        job.save(update_fields=['state'])  # Намерение фиксируется ДО внешнего вызова.
        dispatch_started = True
        result = client.document(job.chat_id, filename, data)
        message_id = result.get('message_id') if isinstance(result, dict) else None
        if not isinstance(message_id, int):
            raise TelegramError('invalid_response', uncertain=True)
        finish_job(job, 'done', message_id=message_id)
    except TelegramError as exc:
        finish_job(job, 'uncertain' if exc.uncertain else 'error', exc.category)
    except (BotDenied, ValidationError):
        finish_job(job, 'uncertain' if dispatch_started else 'error', 'access_or_document')
    except Exception:
        # В журнал не включаем чужие исключения: они могут содержать HTTP URL с ключом.
        finish_job(job, 'uncertain' if dispatch_started else 'error', 'internal')
    if job.state == 'error':
        try:
            access = StaffBotAccess.objects.get(pk=job.access_id)
            check_access(access)
            if access.telegram_user_id == job.chat_id:
                client.message(job.chat_id, 'Не удалось сформировать или отправить прайс. Проверьте доступ и повторите запрос позже.')
        except (TelegramError, BotDenied, StaffBotAccess.DoesNotExist):
            pass


def recover_interrupted(bot_id):
    """Вызывается только после получения эксклюзивной аренды и блокировки процесса."""
    for job in StaffBotJob.objects.filter(bot_id=bot_id, state__in=['generating', 'sending']):
        finish_job(job, 'uncertain' if job.state == 'sending' else 'error', 'interrupted')
