"""Автовыдача публичных прайсов в явно привязанные группы цифровых покупателей.

Событие создаётся в транзакции успешного обновления. Получатель всегда берётся
из BuyerBalanceChat; входящий текст, ID из сообщения и группы поставщиков
не могут назначить адресата. Telegram вызывается только цифровым worker.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from telegram_bots.access import BotDenied, check_function_access
from telegram_bots.client import TelegramError
from telegram_bots.menu import DIGITAL_PRICES
from telegram_bots.models import StaffBotAccess
from digital_sales.models import BuyerBalanceChat, DigitalBot, Notification, Supplier
from .models import AuditEvent, BuyerPriceDispatch, BuyerPriceDispatchPage, CatalogState, Integration, SyncJob

# После доставки страница проходит жизненный цикл закрепа. Во всех этих
# состояниях фото уже подтверждено Telegram и больше не отправляется повторно.
DELIVERED_STATES = ('done', 'pinned', 'unpinned')


def alert_allowed(access):
    try:
        check_function_access(access, DIGITAL_PRICES.code)
        return True
    except BotDenied:
        return False


def staff_alert(event, text):
    """Общие сообщения без сырых ошибок, реквизитов и внутренних цен."""
    for access in StaffBotAccess.objects.filter(allowed=True, revoked_at__isnull=True, telegram_user_id__isnull=False):
        if alert_allowed(access):
            Notification.objects.get_or_create(access=access, event_key=('price_dispatch:' + event)[:100],
                                               defaults={'text': text[:3900]})


def sync_failed(job, *, retry=False):
    staff_alert(f'sync:{job.pk}:' + ('retry' if retry else 'failed'), '⚠️ Не удалось обновить цифровые прайсы. '
                'Прайсы покупателям не отправлены.' + (' CRM повторит обновление автоматически.' if retry else
                ' Проверьте обновление на странице цифровых товаров.'))


def enqueue_after_sync(job):
    """Вызывать внутри apply_catalog, только для нового завершённого SyncJob."""
    if job.state != 'done' or job.active:
        return
    if job.summary.get('manual_sheet', {}).get('error'):
        sync_failed(job)
        return
    accesses = list(StaffBotAccess.objects.select_related('user').filter(
        allowed=True, revoked_at__isnull=True, telegram_user_id__isnull=False).order_by('-user__is_superuser', 'pk'))
    actor = next((access.user for access in accesses if alert_allowed(access)), None)
    chats = BuyerBalanceChat.objects.filter(buyer__isnull=False).select_related('buyer')
    if not actor:
        # Нет авторизованного генератора — запрещено обходить права системным User.
        return
    for chat in chats:
        BuyerPriceDispatch.objects.get_or_create(sync_job=job, buyer=chat.buyer,
                                                 defaults={'chat': chat, 'actor': actor})


def _lease(owner):
    bot = DigitalBot.objects.get(pk=1)
    if not bot.enabled or bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now():
        raise TelegramError('lease_lost')


def _current(row):
    """Не отправляем устаревший снимок или прайс при незавершённом обновлении."""
    config = Integration.objects.get(pk=1)
    state = CatalogState.objects.get(pk=1)
    if (not config.enabled or config.error_category or config.manual_sheet_enabled and config.manual_sheet_error_category
            or SyncJob.objects.filter(active=True).exists() or state.source_at != row.sync_job.finished_at):
        raise TelegramError('catalog_changed')
    chat = BuyerBalanceChat.objects.get(pk=row.chat_id)
    if chat.buyer_id != row.buyer_id or chat.pk >= 0 or any(chat.pk in supplier.chat_ids for supplier in Supplier.objects.all()):
        raise TelegramError('binding_changed')
    if row.bundle_id and row.bundle.buyer_id != row.buyer_id:
        raise TelegramError('binding_changed')
    from .services import require
    require(row.actor, 'download_prices')
    if not any(alert_allowed(access) for access in StaffBotAccess.objects.filter(user=row.actor)):
        raise PermissionDenied('Авторизация генератора отозвана.')
    return chat


def _public_only(bundle):
    """Не пускаем внутренние поля и служебные подписи в клиентский рендер."""
    import json
    import re
    snapshot = bundle.public_snapshot
    allowed = {'revision', 'generated_at', 'source_at', 'stale', 'rows', 'page_titles'}
    row_fields = {'name', 'category', 'section', 'region', 'price', 'availability',
                  'family', 'subgroup', 'label', 'region_label', 'order'}
    if (not isinstance(snapshot, dict) or set(snapshot) - allowed or not isinstance(snapshot.get('rows'), (list, tuple))
            or any(not isinstance(row, dict) or set(row) - row_fields for row in snapshot['rows'])):
        raise TelegramError('private_content')
    text = json.dumps(bundle.public_snapshot, ensure_ascii=False)
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    if re.search(r'pan[\W_]*yan|yan[\W_]*store|пан[\W_]*ян|ян[\W_]*стор|(?:pv2|ov2|qv2)_[\w-]+|https?://|www\.', text, re.I):
        raise TelegramError('private_content')
    if re.search(r'pan\s*yan|yan\s*store|себестоим|наценк|purchase_cost|markup|manual_cost|cost_percent|cost_coefficient', text, re.I):
        raise TelegramError('private_content')


@transaction.atomic
def recover_dispatches():
    """Один цифровой исполнитель: между циклами незавершённая отправка неизвестна."""
    for row in BuyerPriceDispatch.objects.select_for_update().filter(state='working'):
        sending = list(row.deliveries.filter(state='sending'))
        for page in sending:
            page.state, page.error_category = 'uncertain', 'interrupted'
            page.save(update_fields=['state', 'error_category'])
        row.state = 'uncertain' if sending else 'queued'
        row.error_category = 'interrupted' if sending else ''
        row.save(update_fields=['state', 'error_category'])
        if sending:
            staff_alert(f'delivery:{row.pk}', '⚠️ Отправка цифрового прайса прервалась. '
                        'Проверьте чат покупателя: автоматического повтора неизвестной отправки не будет.')


def _pin_one(client, row, *, owner, bot_id):
    """Сначала закрепляем весь новый комплект, затем снимаем только свои старые.

    Один pin/unpin за цикл. Эти операции повторяемы с тем же message_id:
    прерывание после ответа Telegram не приводит к повторной отправке картинки.
    """
    from digital_sales.chat_balances import _rights
    if (not row.deliveries.exists() or row.deliveries.exclude(state__in=DELIVERED_STATES).exists()
            or row.deliveries.filter(message_id__isnull=True).exists()):
        raise TelegramError('incomplete_bundle')
    _lease(owner)
    chat = _current(row)
    rights = _rights(client, chat.pk, bot_id)
    if rights.get('status') != 'creator' and not (rights.get('status') == 'administrator' and rights.get('can_pin_messages') is True):
        raise TelegramError('pin_permission')
    _lease(owner)
    _current(row)
    image = row.deliveries.filter(state='done').order_by('page__index').first()
    if image:
        result = client.call('pinChatMessage', {'chat_id': chat.pk, 'message_id': image.message_id,
                                               'disable_notification': True})
        if result is not True:
            raise TelegramError('invalid_response')
        image.state = 'pinned'
        image.save(update_fields=['state'])
        return False
    # Не используем unpinAllChatMessages и не трогаем произвольные закрепы чата.
    old = (BuyerPriceDispatchPage.objects.filter(dispatch__chat_id=row.chat_id,
           dispatch__buyer_id=row.buyer_id, dispatch_id__lt=row.pk, state='pinned', message_id__isnull=False)
           .order_by('pk').first())
    if old:
        result = client.call('unpinChatMessage', {'chat_id': chat.pk, 'message_id': old.message_id})
        if result is not True:
            raise TelegramError('invalid_response')
        old.state = 'unpinned'
        old.save(update_fields=['state'])
        return False
    return True


@transaction.atomic
def queue_current_pins(*, actor):
    """Явное включение закрепов для уже доставленных актуальных комплектов."""
    from .services import require
    actor = require(actor, 'configure_integration')
    source_at = CatalogState.objects.get(pk=1).source_at
    queued = []
    for row in BuyerPriceDispatch.objects.select_for_update().filter(state__in=('done', 'error'), sync_job__finished_at=source_at):
        _current(row)
        if (not row.deliveries.exists() or row.deliveries.exclude(state__in=DELIVERED_STATES).exists()
                or row.deliveries.filter(message_id__isnull=True).exists() or not row.deliveries.filter(state='done').exists()):
            continue
        row.state, row.attempts, row.error_category = 'pinning', 0, ''
        row.next_attempt_at = row.finished_at = None
        row.save(update_fields=['state', 'attempts', 'error_category', 'next_attempt_at', 'finished_at'])
        AuditEvent.objects.create(actor=actor, kind='pin_current_price', detail={'dispatch': row.pk})
        queued.append(row.pk)
    return queued


def publish_one(client, *, owner, bot_id, renew=None):
    """Не более одного изображения за цикл, чтобы бот продолжал принимать заказы."""
    with transaction.atomic():
        _lease(owner)
        row = (BuyerPriceDispatch.objects.select_for_update().filter(state__in=('queued', 'pinning'))
               .filter(next_attempt_at__isnull=True).order_by('pk').first())
        if row is None:
            row = (BuyerPriceDispatch.objects.select_for_update().filter(state__in=('queued', 'pinning'), next_attempt_at__lte=timezone.now())
                   .order_by('pk').first())
        if not row:
            return False
        row.state, row.owner, row.attempts = 'working', owner, row.attempts + 1
        row.save(update_fields=['state', 'owner', 'attempts'])
    page, sending, pinning = None, False, False
    try:
        _current(row)
        if row.bundle_id is None:
            from .bundles import generate_bundle
            from .presentation import page_caption
            if renew:
                renew()
            bundle = generate_bundle(actor=row.actor, buyer=row.buyer)
            if renew:
                renew()
            with transaction.atomic():
                _lease(owner)
                _current(row)
                row.bundle = bundle
                _public_only(bundle)
                row.save(update_fields=['bundle'])
                pages = list(bundle.pages.all())
                for image in pages:
                    BuyerPriceDispatchPage.objects.create(dispatch=row, page=image,
                        caption=page_caption(bundle, image, len(pages)))
        page = row.deliveries.select_related('page').filter(state='pending').order_by('page__index').first()
        if page:
            from digital_sales.chat_balances import _rights
            from .telegram import requires_document
            _lease(owner)
            chat = _current(row)
            _public_only(row.bundle)
            content = bytes(page.page.png)
            if (page.page.bundle_id != row.bundle_id or not content.startswith(b'\x89PNG\r\n\x1a\n')
                    or len(content) >= 50 * 1024 * 1024):
                raise TelegramError('invalid_image')
            if renew:
                renew()
            _rights(client, chat.pk, bot_id)
            # Проверка привязки и свежести ещё раз после сетевого получения прав.
            with transaction.atomic():
                _lease(owner)
                _current(row)
                page.state = 'sending'
                page.save(update_fields=['state'])
            sending = True
            method, field = ('sendDocument', 'document') if requires_document(page.page) else ('sendPhoto', 'photo')
            result = client.call(method, {'chat_id': chat.pk, 'caption': page.caption},
                                 files={field: (page.page.filename, content, 'image/png')})
            if not isinstance(result, dict) or type(result.get('message_id')) is not int or result['message_id'] <= 0:
                raise TelegramError('invalid_response', uncertain=True)
            page.message_id, page.state = result['message_id'], 'done'
            page.save(update_fields=['message_id', 'state'])
            sending = False
        if page:
            remaining = row.deliveries.exclude(state__in=DELIVERED_STATES).exists()
            row.state = 'queued' if remaining else 'pinning'
        else:
            pinning = True
            if renew:
                renew()
            row.state = 'done' if _pin_one(client, row, owner=owner, bot_id=bot_id) else 'pinning'
        row.error_category, row.next_attempt_at, row.attempts = '', None, 0
        row.finished_at = timezone.now() if row.state == 'done' else None
        row.save(update_fields=['state', 'error_category', 'next_attempt_at', 'finished_at', 'attempts'])
    except OperationalError:
        # После ошибки БД мог потеряться результат уже отправленного сообщения.
        # Следующий цикл восстановит состояние без повторного сетевого запроса.
        raise
    except Exception as exc:
        category = getattr(exc, 'category', None) or getattr(exc, 'code', None) or 'generation'
        uncertain = sending and (not isinstance(exc, TelegramError) or exc.uncertain or
                                  category in ('timeout', 'network', 'invalid_response'))
        retry = not uncertain and category in ('timeout', 'network', 'rate_limited') and row.attempts < 5
        if page and page.state == 'sending':
            page.state, page.error_category = ('uncertain' if uncertain else 'pending' if retry else 'error'), category
            page.save(update_fields=['state', 'error_category'])
        row.state = 'uncertain' if uncertain else 'queued' if retry else 'skipped' if category in ('catalog_changed', 'binding_changed', 'no_priced_blocks') else 'error'
        row.error_category = category
        row.next_attempt_at = timezone.now() + timedelta(seconds=min(300, 15 * row.attempts)) if retry else None
        row.finished_at = None if retry else timezone.now()
        row.save(update_fields=['state', 'error_category', 'next_attempt_at', 'finished_at'])
        if not retry and category != 'catalog_changed':
            from .public import safe_text
            staff_alert(f'delivery:{row.pk}', ('⚠️ Не удалось обновить закреп цифрового прайса покупателя «' if pinning else
                        '⚠️ Не удалось отправить цифровой прайс покупателю «') + safe_text(row.buyer.name) +
                        ('». Проверьте права бота на закрепление сообщений. Изображения повторно отправляться не будут.' if pinning else
                         '». Проверьте его чат и настройки цифровых товаров.') +
                        (' Автоматического повтора неизвестной отправки не будет.' if uncertain else ''))
    return True
