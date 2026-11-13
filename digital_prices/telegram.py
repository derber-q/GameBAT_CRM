"""Одна кнопка — весь PNG-комплект. Результат каждой фотографии фиксируется отдельно."""
from django.db import transaction
import time
from django.core.exceptions import ValidationError
from telegram_bots.client import TelegramError
from telegram_bots.access import BotDenied
from .models import BotBundle, PageDelivery, BuyerPriceRequest
from .bundles import generate_bundle
from .presentation import page_caption


def requires_document(page):
    """Высокие прайсы сохраняют исходные пиксели; остальные проходят лимиты фото."""
    return (page.height>2600 or len(page.png)>=10*1024*1024 or page.width+page.height>10000
            or max(page.width/page.height,page.height/page.width)>20)


def finish(job, category=''):
    from telegram_bots.jobs import finish_job
    states = list(PageDelivery.objects.filter(job=job).values_list('state', flat=True))
    state = ('done' if states and all(s == 'done' for s in states) else
             'uncertain' if any(s in ('sending', 'uncertain') for s in states) else
             'partial' if 'done' in states else 'error')
    finish_job(job, state, '' if state == 'done' else category)


def notify_result(job, client):
    if job.state == 'done':
        return
    from telegram_bots.jobs import _check_job_access
    try:
        _check_job_access(job)
        known = list(PageDelivery.objects.filter(job=job, state='done').order_by('page__index').values_list('page__index', flat=True))
        done = len(known)
        total = PageDelivery.objects.filter(job=job).count()
        if not total:
            client.message(job.chat_id, 'Для этого покупателя пока нет блоков с заполненной наценкой. '
                'Укажите общие или индивидуальные наценки в CRM.' if job.error_category == 'no_priced_blocks' else
                'Не удалось сформировать комплект GameBAT. Проверьте сохранённый каталог в CRM.')
            return
        indices = ', '.join(map(str, known)) if done < 40 else f'{known[0]}–{known[-1]}'
        client.message(job.chat_id, f'Комплект GameBAT не отправлен полностью: подтверждено {done} из {total} страниц. '
            f'Подтверждённые страницы: {indices or "нет"}. '
            'Проверьте чат. Автоматического повтора неизвестной отправки не будет.')
    except (BotDenied, TelegramError):
        pass


def recover_job(job):
    for page in PageDelivery.objects.filter(job=job, state='sending'):
        page.state, page.error_category = 'uncertain', 'interrupted'
        page.save(update_fields=['state', 'error_category'])
    finish(job, 'interrupted')


def run_job(job, client, *, owner=None):
    from telegram_bots.jobs import _check_job_access, finish_job
    dispatch_started, current = False, None
    try:
        _, user = _check_job_access(job, owner)
        link = BotBundle.objects.filter(job=job).first()
        if link is None:
            request = BuyerPriceRequest.objects.select_related('buyer').filter(job=job).first()
            if request is None:
                raise ValidationError('Откройте меню и выберите покупателя для цифрового прайса.')
            bundle = generate_bundle(actor=user, buyer=request.buyer)
            with transaction.atomic():
                link = BotBundle.objects.create(job=job, bundle=bundle)
                for page in bundle.pages.all():
                    PageDelivery.objects.create(job=job, page=page)
        job.state = 'sending'
        job.save(update_fields=['state'])
        total = PageDelivery.objects.filter(job=job).count()
        for current in PageDelivery.objects.filter(job=job).select_related('page').order_by('page__index'):
            if current.state == 'done':
                continue
            if current.state != 'pending':
                break
            if PageDelivery.objects.filter(job=job, state='done').exists():
                time.sleep(1.05)  # Последовательные фотографии в одном личном чате.
            _check_job_access(job, owner)
            current.state = 'sending'
            current.save(update_fields=['state'])
            dispatch_started = True
            sender = client.image_document if requires_document(current.page) else client.photo
            response = sender(job.chat_id, current.page.filename, bytes(current.page.png),
                              caption=page_caption(link.bundle, current.page, total))
            if not isinstance(response, dict) or type(response.get('message_id')) is not int or response['message_id'] <= 0:
                raise TelegramError('invalid_response', uncertain=True)
            current.state, current.message_id = 'done', response['message_id']
            current.save(update_fields=['state', 'message_id'])
            dispatch_started = False
        finish(job)
    except Exception as exc:
        category = (exc.category if isinstance(exc, (TelegramError, BotDenied)) else
                    'no_priced_blocks' if isinstance(exc, ValidationError) and getattr(exc, 'code', None) == 'no_priced_blocks' else 'generation_or_internal')
        uncertain = dispatch_started and (not isinstance(exc, TelegramError) or exc.uncertain or exc.category in ('network', 'timeout', 'invalid_response'))
        if current and current.state == 'sending':
            current.state, current.error_category = 'uncertain' if uncertain else 'error', category
            current.save(update_fields=['state', 'error_category'])
        if PageDelivery.objects.filter(job=job).exists():
            finish(job, category)
        else:
            finish_job(job, 'error', category)
    notify_result(job, client)
