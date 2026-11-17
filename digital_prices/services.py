"""Каталог и фиксированные наценки. Ни один сервис не меняет склад или деньги."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from core.db_retry import retry_database_lock
from core.external_policy import require_live_operation
from .api import APIError, CatalogClient, amount
from .models import Product, Integration, CatalogState, SyncJob, AuditEvent, ManualPriceEntry
from .classification import characteristics
from .sheet_source import SheetClient, SheetSourceError, normalized_label

CATEGORIES = {'ps': 'PlayStation Plus', 'xbox': 'Подписки Xbox', 'code': 'Цифровые коды',
    'empty': 'Аккаунты', 'steam_topup': 'Пополнение Steam', 'game': 'Игры PlayStation',
    'xbox_game': 'Игры Xbox', 'steam_gift': 'Подарки Steam', 'cprod': 'Цифровые услуги'}


def require(actor, permission):
    user = get_user_model().objects.filter(pk=getattr(actor, 'pk', None), is_active=True).first()
    if not user or not user.has_perm('digital_prices.' + permission):
        raise PermissionDenied('Нет разрешения на это действие с цифровыми ценами.')
    return user


def ready():
    """До приёмки миграций функция не появляется даже у superuser."""
    try:
        return CatalogState.objects.filter(pk=1).exists()
    except (OperationalError, ProgrammingError):
        return False


def selling_price(cost, currency, markup, rule):
    if cost is None or markup is None or currency != 'RUB':
        return None
    step = Decimal(50 if rule in (Product.Rule.PS_PLUS, Product.Rule.XBOX) else 10)
    return ((cost + markup) / step).to_integral_value(rounding=ROUND_CEILING) * step


def effective_rule(product):
    """EA Play для PlayStation округляется до 50 ₽ и у ранее загруженных карточек.

    Используется существующее правило подписок: менять себестоимость, снимки
    документов или настройки остальных товаров для исправления не требуется.
    """
    if product.source_type == 'ps':
        _, plan, _ = characteristics(product.source_type, product.source_name, product.attributes)
        if plan == 'EA Play':
            return Product.Rule.PS_PLUS
    return product.rule


def product_price(product):
    return selling_price(product.purchase_cost, product.currency, product.markup, effective_rule(product))


@retry_database_lock
@transaction.atomic
def edit_product(*, actor, product_id, revision, values):
    if not values:
        raise ValidationError('Не указаны поля изменения.')
    actor = require(actor, 'edit_markup' if 'markup' in values else 'edit_layout')
    if set(values) - {'markup', 'display_name', 'category', 'section', 'position', 'rule'}:
        raise ValidationError('Недопустимые поля изменения.')
    if 'markup' in values:
        require(actor, 'edit_markup')
    if set(values) - {'markup'}:
        require(actor, 'edit_layout')
    state = CatalogState.objects.select_for_update().get(pk=1)
    row = Product.objects.select_for_update().get(pk=product_id)
    if str(row.revision) != str(revision):
        raise ValidationError('Позиция уже изменилась. Обновите строку перед сохранением.', code='conflict')
    for key, value in values.items():
        if key == 'markup':
            try:
                value = None if value in ('', None) else amount(value)
            except APIError:
                raise ValidationError('Укажите неотрицательную сумму в рублях с точностью до копейки.') from None
        elif key == 'rule':
            if value not in Product.Rule.values:
                raise ValidationError('Выберите правило округления.')
            row.rule_manual = True
        elif key in ('category', 'section'):
            row.category_manual = True
        if key in ('display_name', 'category'):
            from .public import safe_text
            value = safe_text(value)
        setattr(row, key, value)
    row.edited_by, row.edited_at, row.revision = actor, timezone.now(), row.revision + 1
    row.full_clean()
    row.save()
    state.revision += 1
    state.save(update_fields=['revision'])
    AuditEvent.objects.create(actor=actor, product=row, kind='local_settings', detail={'fields': sorted(values), 'revision': row.revision})
    return row


@transaction.atomic
def apply_catalog(offers, *, job_id, owner, configuration_revision=None,
                  sheet_costs=None, sheet_error='', manual_revisions=None):
    if not offers or len({row.identity for row in offers}) != len(offers):
        raise APIError('empty_or_duplicate_catalog')
    job = SyncJob.objects.select_for_update().get(pk=job_id)
    if job.state != 'running' or job.owner != owner or job.lease_until <= timezone.now():
        raise APIError('lease_lost')
    config = Integration.objects.select_for_update().get(pk=1)
    if not config.enabled:
        raise APIError('disabled')
    if configuration_revision is not None and config.revision != configuration_revision:
        raise APIError('configuration_changed')
    state = CatalogState.objects.select_for_update().get(pk=1)
    now, identities, added = timezone.now(), {offer.identity for offer in offers}, 0
    from .v2_mapping import plan
    matched, ambiguous, missing_legacy = plan(offers, list(Product.objects.select_for_update().all()))
    AuditEvent.objects.create(kind='v2_mapping', detail={'matched': {key: row.pk for key, row in matched.items()},
        'ambiguous': ambiguous, 'missing': missing_legacy})
    for offer in offers:
        row = Product.objects.select_for_update().filter(external_id=offer.identity).first()
        if row is None and offer.identity in matched:
            row = matched[offer.identity]
            row.legacy_external_id, row.external_id = row.external_id, offer.identity
        if row is None:
            row = Product(external_id=offer.identity, markup=None)
            added += 1
        row.source_name, row.source_type = offer.name, offer.kind
        row.platform, row.region, row.attributes = offer.platform, offer.region, offer.attributes
        # Отсутствие новой цены не обнуляет последний подтверждённый снимок.
        if offer.cost is not None:
            row.purchase_cost = offer.cost
        row.currency = offer.currency
        row.api_version = offer.attributes.get('api_version', 0)
        row.fulfillment = offer.attributes.get('fulfillment', '')
        row.requirements = offer.attributes.get('requirements', {})
        row.quantity_limits = offer.attributes.get('limits', {})
        row.mapping_issue = 'ambiguous' if offer.identity in ambiguous else ''
        row.availability = 'yes' if offer.available is True else 'no' if offer.available is False else 'unknown'
        row.requires_review = (offer.currency != 'RUB' or offer.cost is None and offer.kind != 'steam_topup'
                               or offer.available is None or offer.kind not in CATEGORIES)
        row.requires_review = row.requires_review or bool(row.mapping_issue)
        if not row.rule_manual:
            family, plan, _ = characteristics(offer.kind, offer.name, offer.attributes)
            row.rule = (Product.Rule.XBOX if offer.kind == 'xbox' else Product.Rule.PS_PLUS
                if offer.kind == 'ps' and plan in ('Essential', 'Extra', 'Deluxe', 'Premium', 'EA Play') else Product.Rule.OTHER)
        if not row.category_manual:
            family, _, _ = characteristics(offer.kind, offer.name, offer.attributes)
            row.category = (offer.attributes.get('code_category') or CATEGORIES['code']) if offer.kind == 'code' else (
                family if offer.kind == 'cprod' else CATEGORIES.get(offer.kind, 'Другие цифровые предложения'))
            row.section = 'codes' if offer.kind == 'code' else 'services'
        row.last_seen_at = row.confirmed_at = now
        row.revision += 1
        row.save()
    for missing in Product.objects.exclude(external_id__in=identities):
        # Не приравниваем исчезновение из ответа к подтверждённому отсутствию.
        missing.requires_review, missing.revision = True, missing.revision + 1
        missing.save(update_fields=['requires_review', 'revision'])
    state.revision, state.source_at = state.revision + 1, now
    state.save(update_fields=['revision', 'source_at'])
    config.last_success_at, config.error_category = now, ''
    sheet_summary = {}
    if config.manual_sheet_enabled and (sheet_costs is not None or sheet_error):
        from .classification import region_code
        manual_rows=list(ManualPriceEntry.objects.select_for_update().all())
        if not sheet_error and sheet_costs is not None:
            from .sheet_structure import reconcile_sng
            manual_rows, sheet_error = reconcile_sng(manual_rows, sheet_costs, manual_revisions)
        else:
            manual_rows = [row for row in manual_rows if not row.source_archived]
        keys={row.pk:(row.kind,region_code(row.region),normalized_label(row.label)) for row in manual_rows}
        if not sheet_error and sheet_costs is not None and (not manual_rows or not set(keys.values()).intersection(sheet_costs)):
            sheet_error='sheet_mapping'
        if not sheet_error and sheet_costs is not None:
            changed,missing,skipped,absent=0,0,0,0
            for row in manual_rows:
                if manual_revisions is not None and manual_revisions.get(row.pk)!=row.revision:
                    skipped+=1
                    continue  # Сотрудник изменил строку во время сетевого чтения; не затираем его ввод.
                offer=sheet_costs.get(keys[row.pk])
                if offer is None:
                    absent += 1
                    # Старая закупка и индивидуальные наценки остаются в БД;
                    # отсутствующую в источнике строку нельзя выдавать как свежую.
                    if row.sheet_issue != 'source_missing':
                        row.sheet_issue = 'source_missing'
                        row.revision += 1
                        row.save(update_fields=['sheet_issue','revision'])
                    continue
                field={'rub':'manual_cost','percent':'cost_percent','coefficient':'cost_coefficient'}[offer.mode]
                fields=['sheet_reference','sheet_checked_at','sheet_issue']
                old_issue=row.sheet_issue
                row.sheet_reference,row.sheet_checked_at=offer.reference,now
                row.sheet_issue='missing_price' if offer.cost is None else ''
                if offer.cost is None:
                    missing+=1
                elif getattr(row,field)!=offer.cost:
                    setattr(row,field,offer.cost)
                    fields.append(field)
                    changed+=1
                if len(fields)>3 or old_issue!=row.sheet_issue:
                    row.revision+=1
                    fields.append('revision')
                # Автосинхронизация не выдаёт себя за ручного редактора:
                # у исходных/seed-тарифов edited_by закономерно отсутствует.
                row.full_clean(exclude=['edited_by'] if row.edited_by_id is None else None)
                row.save(update_fields=fields)
            config.manual_sheet_last_success_at=now
            sheet_error='sheet_local_changes' if skipped else 'sheet_prices_missing' if missing else ''
            sheet_summary={'updated':changed,'missing':missing,'skipped':skipped,'matched':len(manual_rows)-absent,
                           'source_missing':absent}
            AuditEvent.objects.create(kind='sheet_costs_applied',detail={'job':str(job.pk),**sheet_summary})
        config.manual_sheet_error_category=sheet_error
    config.save(update_fields=['last_success_at','error_category','manual_sheet_last_success_at','manual_sheet_error_category'])
    job.state, job.active, job.finished_at, job.item_count = 'done', False, now, len(offers)
    job.summary = {'added': added, 'updated': len(offers)-added,
                   'unavailable': Product.objects.filter(availability='no').count(),
                   'review': Product.objects.filter(requires_review=True).count()}
    if config.manual_sheet_enabled:
        job.summary['manual_sheet']={**sheet_summary,'error':sheet_error}
    job.error_category, job.lease_until = '', None
    job.save(update_fields=['state', 'active', 'finished_at', 'item_count', 'summary', 'error_category', 'lease_until'])
    AuditEvent.objects.create(kind='catalog_applied', detail={'job': str(job.pk), 'items': len(offers), 'revision': state.revision})
    from .dispatch import enqueue_after_sync
    enqueue_after_sync(job)


def next_daily(config, now):
    if not config.daily_enabled or not config.daily_at:
        return None
    zone = ZoneInfo(config.timezone_name)
    local = now.astimezone(zone)
    candidate = datetime.combine(local.date(), config.daily_at, zone)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(ZoneInfo('UTC'))


@transaction.atomic
def save_configuration(*, actor, revision, enabled, daily_enabled, daily_at, timezone_name, api_key='',
                       manual_sheet_enabled=None, manual_sheet_url=None):
    actor = require(actor, 'configure_integration')
    row, _ = Integration.objects.get_or_create(pk=1)
    row = Integration.objects.select_for_update().get(pk=1)
    if str(row.revision) != str(revision):
        raise ValidationError('Настройки изменились. Обновите страницу.')
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError('Укажите существующую часовую зону.') from None
    if daily_enabled and daily_at is None:
        raise ValidationError('Выберите время ежедневного обновления.')
    if api_key:
        if '\n' in api_key or '\r' in api_key or len(api_key) > 500:
            raise ValidationError('API-ключ имеет недопустимый формат.')
        require_live_operation('digital_prices_credentials')
        from integrations.crypto import encrypt_secret
        row.encrypted_key = encrypt_secret(api_key.strip())
    if enabled and not row.encrypted_key:
        raise ValidationError('Для включения нужен API-ключ.')
    if manual_sheet_url is not None:
        if manual_sheet_url:
            from .sheet_source import spreadsheet_id, SheetSourceError
            try:
                spreadsheet_id(manual_sheet_url)
            except SheetSourceError:
                raise ValidationError('Укажите HTTPS-ссылку на таблицу Google Sheets.') from None
        row.manual_sheet_url = str(manual_sheet_url or '').strip()
    if manual_sheet_enabled is not None:
        row.manual_sheet_enabled = bool(manual_sheet_enabled)
    if row.manual_sheet_enabled and not row.manual_sheet_url:
        raise ValidationError('Укажите таблицу ручных тарифов перед включением.')
    row.enabled, row.daily_enabled, row.daily_at, row.timezone_name = enabled, daily_enabled, daily_at, timezone_name
    row.next_at, row.revision = next_daily(row, timezone.now()), row.revision + 1
    row.save()
    AuditEvent.objects.create(actor=actor, kind='configuration', detail={'enabled': enabled, 'daily': daily_enabled})
    return row


@transaction.atomic
def enqueue_sync(*, actor=None, source='manual'):
    if actor:
        actor = require(actor, 'sync_catalog')
    config = Integration.objects.select_for_update().get(pk=1)
    if not config.enabled or not config.encrypted_key:
        raise ValidationError('Обновление не включено или не настроены реквизиты.')
    job = SyncJob.objects.filter(active=True).first()
    return job or SyncJob.objects.create(source=source, requested_by=actor, run_after=timezone.now())


def expected_status():
    from django.conf import settings
    if settings.GAMEBAT_ENV == 'local_test':
        return 'disabled'
    try:
        row = Integration.objects.filter(pk=1).first()
        return 'required' if row and row.enabled and row.encrypted_key else 'disabled' if row else 'unconfigured'
    except (OperationalError, ProgrammingError):
        return 'unconfigured'


def process_one(*, client_factory=CatalogClient, sheet_client_factory=SheetClient):
    require_live_operation('digital_prices_worker')
    if expected_status() != 'required':
        return False
    now, owner = timezone.now(), uuid.uuid4()
    with transaction.atomic():
        config = Integration.objects.select_for_update().get(pk=1)
        if config.daily_enabled and (not config.next_at or config.next_at <= now):
            enqueue_sync(source='daily')
            config.next_at = next_daily(config, now)
            config.save(update_fields=['next_at'])
        job = SyncJob.objects.select_for_update().filter(active=True).first()
        if not job or job.run_after > now or job.state == 'running' and job.lease_until and job.lease_until > now:
            return False
        if job.attempts >= 5:
            job.state, job.active, job.error_category, job.finished_at = 'error', False, 'attempt_limit', now
            job.save(update_fields=['state', 'active', 'error_category', 'finished_at'])
            from .dispatch import sync_failed
            sync_failed(job)
            return True
        job.state, job.owner, job.attempts = 'running', owner, job.attempts + 1
        job.lease_until = now + timedelta(minutes=2)
        job.last_attempt_at = now
        job.save(update_fields=['state', 'owner', 'attempts', 'lease_until', 'last_attempt_at'])
        encrypted_key = config.encrypted_key
        configuration_revision = config.revision
        sheet_url = config.manual_sheet_url if config.manual_sheet_enabled else ''
        manual_revisions = dict(ManualPriceEntry.objects.values_list('pk','revision')) if sheet_url else None
        AuditEvent.objects.create(kind='sync_started', detail={'job': str(job.pk), 'attempt': job.attempts})

    def heartbeat():
        with transaction.atomic():
            current = SyncJob.objects.select_for_update().get(pk=job.pk)
            if current.owner != owner or current.state != 'running':
                raise APIError('lease_lost')
            current.lease_until = timezone.now() + timedelta(minutes=2)
            current.save(update_fields=['lease_until'])

    client = None
    sheet_client = None
    try:
        from integrations.crypto import decrypt_secret
        client = client_factory(decrypt_secret(encrypted_key))
        offers = client.fetch(heartbeat=heartbeat, include_codes=True)
        heartbeat()
        sheet_costs,sheet_error=None,''
        if sheet_url:
            try:
                sheet_client=sheet_client_factory(sheet_url)
                sheet_costs=sheet_client.fetch_costs()
            except SheetSourceError as exc:
                if exc.category in ('sheet_network','sheet_rate_limited','sheet_unavailable'):
                    raise APIError(exc.category, 120 if exc.category == 'sheet_rate_limited' else 60) from None
                sheet_error=exc.category
            except Exception:
                sheet_error='sheet_internal'
            heartbeat()
        apply_catalog(offers, job_id=job.pk, owner=owner, configuration_revision=configuration_revision,
                      sheet_costs=sheet_costs,sheet_error=sheet_error,manual_revisions=manual_revisions)
    except Exception as exc:
        # Сырые исключения requests/ключи не записываем ни в журнал, ни в HTML.
        category = exc.category if isinstance(exc, APIError) else 'configuration_or_internal'
        delay = exc.retry_after if isinstance(exc, APIError) else 0
        with transaction.atomic():
            stored = SyncJob.objects.select_for_update().get(pk=job.pk)
            if stored.owner == owner:
                retry = bool(delay and stored.attempts < 5)
                stored.state, stored.active, stored.error_category = 'pending' if retry else 'error', retry, category
                stored.run_after, stored.finished_at = timezone.now() + timedelta(seconds=delay), None if retry else timezone.now()
                stored.save(update_fields=['state', 'active', 'error_category', 'run_after', 'finished_at'])
                config = Integration.objects.select_for_update().get(pk=1)
                config.error_category = category
                config.save(update_fields=['error_category'])
                AuditEvent.objects.create(kind='sync_failed', detail={'job': str(job.pk), 'attempt': stored.attempts,
                                                                      'category': category, 'retry': retry})
                from .dispatch import sync_failed
                sync_failed(stored, retry=retry)
    finally:
        if client:
            client.close()
        if sheet_client:
            sheet_client.close()
    return True
