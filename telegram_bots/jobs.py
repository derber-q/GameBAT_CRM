"""Один исполнитель XLSX, отдельный от polling. Неопределённая отправка не повторяется."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from .access import check_access, check_function_access, BotDenied
from .client import TelegramError
from .documents import wholesale_document, supplier_documents
from .menu import WHOLESALE, SUPPLIER_TEMPLATES
from .models import StaffBotJob, StaffBotAccess, StaffBotJobDocument
from partners.models import Supplier


@retry_database_lock
@transaction.atomic
def claim_job(bot_id):
    job = StaffBotJob.objects.select_for_update().filter(bot_id=bot_id, state='queued').first()
    if job:
        job.state, job.started_at = 'generating', timezone.now()
        job.save(update_fields=['state', 'started_at'])
    return job


@retry_database_lock
def finish_job(job, state, category='', message_id=None):
    job.state, job.error_category = state, category
    job.finished_at, job.telegram_message_id = timezone.now(), message_id
    job.save(update_fields=['state', 'error_category', 'finished_at', 'telegram_message_id'])


def run_job(job, client, *, owner=None):
    if job.state != 'generating':
        return
    if job.function == SUPPLIER_TEMPLATES.code:
        return _run_supplier_job(job, client, owner=owner)
    return _run_wholesale_job(job, client, owner=owner)


def _check_job_access(job, owner=None):
    access = StaffBotAccess.objects.get(pk=job.access_id)
    user = check_function_access(access, job.function)
    if access.bot_id != job.bot_id or access.telegram_user_id != job.chat_id:
        raise BotDenied()
    if owner is not None:
        bot = access.bot
        if bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now():
            raise BotDenied()
    if job.function == SUPPLIER_TEMPLATES.code and not Supplier.objects.filter(pk=job.supplier_id).exists():
        raise BotDenied('supplier_missing', 'Поставщик не найден. Откройте список заново.')
    return access, user


def _run_wholesale_job(job, client, *, owner=None):
    dispatch_started = False
    try:
        access, _ = _check_job_access(job, owner)
        filename, data = wholesale_document(access, job.warehouse_id)
        # Проверяем свежую привязку и permissions непосредственно перед отправкой.
        _check_job_access(job, owner)
        job.state = 'sending'
        job.save(update_fields=['state'])  # Намерение фиксируется ДО внешнего вызова.
        dispatch_started = True
        result = client.document(job.chat_id, filename, data)
        message_id = result.get('message_id') if isinstance(result, dict) else None
        if not isinstance(message_id, int) or isinstance(message_id, bool) or message_id <= 0:
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
            check_function_access(access, WHOLESALE.code)
            if access.telegram_user_id == job.chat_id:
                client.message(job.chat_id, 'Не удалось сформировать или отправить прайс. Проверьте доступ и повторите запрос позже.')
        except (TelegramError, BotDenied, StaffBotAccess.DoesNotExist):
            pass


@retry_database_lock
def finish_document(document, state, category='', message_id=None):
    document.state, document.error_category = state, category
    document.finished_at, document.telegram_message_id = timezone.now(), message_id
    document.save(update_fields=['state', 'error_category', 'finished_at', 'telegram_message_id'])


def _send_supplier_document(document, client, chat_id, filename, content):
    dispatch_started = False
    try:
        document.state, document.started_at = 'sending', timezone.now()
        document.save(update_fields=['state', 'started_at'])
        dispatch_started = True  # Намерение уже сохранено; повторять HTTP-вызов нельзя.
        result = client.document(chat_id, filename, content)
        message_id = result.get('message_id') if isinstance(result, dict) else None
        if not isinstance(message_id, int) or isinstance(message_id, bool) or message_id <= 0:
            raise TelegramError('invalid_response', uncertain=True)
        finish_document(document, 'done', message_id=message_id)
        return True
    except TelegramError as exc:
        finish_document(document, 'uncertain' if exc.uncertain else 'error', exc.category)
    except Exception:
        # В том числе отказ записи подтверждения после внешнего успешного ответа.
        finish_document(document, 'uncertain' if dispatch_started else 'error', 'internal')
    return False


def _finish_supplier_job(job, category=''):
    states = list(job.documents.values_list('state', flat=True))
    if len(states) == 2 and all(state == 'done' for state in states):
        state = 'done'
    elif any(state in ['sending', 'uncertain'] for state in states):
        state = 'uncertain'
    elif 'done' in states:
        state = 'partial'
    else:
        state = 'error'
    finish_job(job, state, '' if state == 'done' else category)


def _notify_supplier_result(job, client):
    if job.state == 'done':
        return
    if job.state == 'uncertain':
        text = ('Результат отправки одного из файлов неизвестен. Проверьте чат. '
            'Автоматической повторной отправки не будет. При необходимости запросите комплект заново.')
    elif job.state == 'partial':
        text = ('Шаблоны отправлены частично. Проверьте полученные файлы в чате. '
            'Дальнейшая отправка остановлена. При необходимости запросите новый комплект вручную.')
    elif job.error_category == 'generation':
        text = 'Не удалось сформировать шаблоны. Попробуйте позже.'
    elif job.error_category == 'supplier_missing':
        text = 'Поставщик не найден. Откройте список заново.'
    else:
        text = 'Не удалось отправить шаблоны. Проверьте доступ и повторите запрос позже.'
    try:
        access = StaffBotAccess.objects.get(pk=job.access_id)
        check_access(access)
        if access.telegram_user_id == job.chat_id:
            client.message(job.chat_id, text)
    except (TelegramError, BotDenied, StaffBotAccess.DoesNotExist):
        pass


def _run_supplier_job(job, client, *, owner=None):
    category = 'generation'
    try:
        access, _ = _check_job_access(job, owner)
        rows = {row.product_kind: row for row in job.documents.all()}
        if set(rows) != {'cd', 'tech'}:
            raise ValidationError('Не найден комплект документов задания.')
        if any(row.state != 'pending' for row in rows.values()):
            # Исполнитель не продолжает комплект, в котором уже была попытка отправки.
            _recover_supplier_job(job)
            _notify_supplier_result(job, client)
            return
        documents = supplier_documents(access, job.supplier_id)  # Оба XLSX до первого sendDocument.
        job.state = 'sending'
        job.save(update_fields=['state'])
        category = 'delivery'
        for kind, filename, content in documents:
            _check_job_access(job, owner)  # Проверка отдельно перед каждым внешним вызовом.
            if not _send_supplier_document(rows[kind], client, job.chat_id, filename, content):
                category = rows[kind].error_category
                break  # Безопасная политика: первый сбой останавливает оставшийся файл.
    except BotDenied as exc:
        category = exc.category
    except ValidationError:
        category = 'generation'
    except Exception:
        category = 'generation' if job.state == 'generating' else 'internal'
    _finish_supplier_job(job, category)
    _notify_supplier_result(job, client)


def _recover_supplier_job(job):
    for document in job.documents.filter(state='sending'):
        finish_document(document, 'uncertain', 'interrupted')
    _finish_supplier_job(job, 'interrupted')


def recover_interrupted(bot_id):
    """Вызывается только после получения эксклюзивной аренды и блокировки процесса."""
    recovered = []
    for job in StaffBotJob.objects.filter(bot_id=bot_id, state__in=['generating', 'sending']):
        if job.function == SUPPLIER_TEMPLATES.code:
            _recover_supplier_job(job)
            recovered.append(job)
        else:
            finish_job(job, 'uncertain' if job.state == 'sending' else 'error', 'interrupted')
    return recovered


def notify_recovered_jobs(jobs, client):
    """Вызывается только после проверки личности бота и отсутствия webhook."""
    for job in jobs:
        _notify_supplier_result(job, client)
