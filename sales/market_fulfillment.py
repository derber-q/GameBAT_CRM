"""Сборка сканером и последовательность PDF → Windows → готовность Маркета."""
from collections import defaultdict
from datetime import timedelta
import uuid
import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import BarcodeRegistry
from yandex_market.documents import request_labels
from yandex_market.models import OrderMetadata
from yandex_market.orders import request_order_action
from yandex_market.services import audit
from .label_printing import print_pdf, printer_configuration, print_job_completed, release_print_job
from .models import MarketPicking, MarketPrintJob, MarketScanEvent

logger = logging.getLogger('gamebat.business')


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Некорректный идентификатор запроса сканера.') from None


def _check_actor(actor, *, scanning=False):
    permissions = ['yandex_market.print_labels']
    if scanning:
        permissions += ['sales.view_sales', 'yandex_market.manage_orders']
    elif not (actor.has_perm('sales.view_sales') or actor.has_perm('sales.view_sale_detail')):
        raise PermissionDenied
    if not actor.is_active or not all(actor.has_perm(name) for name in permissions):
        raise PermissionDenied


def required_items(order):
    required = defaultdict(int)
    for line in order.lines.select_related('connection'):
        connection = line.connection
        if connection.cd_id:
            key = f'cd:{connection.cd_id}'
        elif connection.tech_id:
            key = f'tech:{connection.tech_id}'
        else:
            raise ValidationError('В заказе есть товар без карточки CRM.')
        required[key] += line.quantity
    sale_items = {f'cd:{row.cd_id}': row.quantity for row in order.sale.cd_items.all()}
    sale_items.update({f'tech:{row.tech_id}': row.quantity for row in order.sale.tech_items.all()})
    if not required or dict(required) != sale_items or order.sale.custom_items.exists():
        raise ValidationError('Состав заказа Маркета отличается от продажи. Нужна сверка перед сборкой.')
    return dict(required)


def record_scan(*, actor, barcode, request_id):
    _check_actor(actor, scanning=True)
    request_id = _uuid(request_id)
    barcode = str(barcode or '').strip()
    if not barcode or len(barcode) > 100:
        raise ValidationError('Некорректный штрихкод.')
    printer = printer_configuration()
    try:
        with transaction.atomic():
            # Первая операция — запись: SQLite сериализует конкурирующие счётчики.
            event = MarketScanEvent.objects.create(request_id=request_id, actor=actor, barcode=barcode)
            entry = BarcodeRegistry.objects.filter(value=barcode).first()
            if not entry or entry.product_kind not in {'cd', 'tech'}:
                raise ValidationError('Штрихкод товара не найден в реестре CRM.')
            key = f'{entry.product_kind}:{entry.cd_id or entry.tech_id}'
            lookup = {f'lines__connection__{entry.product_kind}_id': entry.cd_id or entry.tech_id}
            orders = OrderMetadata.objects.select_related('sale', 'integration').filter(
                **lookup, status='PROCESSING', substatus='STARTED', fake=False, integration__enabled=True,
                sale__cancelled_at__isnull=True, sale__sale_type='yandex_market',
            ).exclude(sale__order_status='delivered', sale__payment_status='paid').exclude(
                print_jobs__ready_after_print=True,
            ).distinct().order_by(F('created_remote_at').asc(nulls_last=True), 'created_at', 'order_id')
            for order in orders:
                required = required_items(order)
                picking, _ = MarketPicking.objects.get_or_create(order=order, defaults={'required': required})
                if picking.required != required:
                    raise ValidationError('Состав заказа изменился во время сборки. Нужна сверка.')
                if picking.scanned.get(key, 0) >= required.get(key, 0):
                    continue
                picking.scanned[key] = picking.scanned.get(key, 0) + 1
                complete = all(picking.scanned.get(product, 0) == count for product, count in required.items())
                if complete:
                    picking.completed_at = timezone.now()
                picking.save(update_fields=['scanned', 'completed_at', 'updated_at'])
                result = {'order_id': order.order_id, 'sale_pk': order.sale_id, 'scanned': sum(picking.scanned.values()),
                          'required': sum(required.values()), 'complete': complete}
                if complete:
                    job = MarketPrintJob.objects.create(order=order, actor=actor, ready_after_print=True, printer_name=printer)
                    result['print_job_id'] = str(job.request_id)
                event.order, event.result = order, result
                event.save(update_fields=['order', 'result'])
                audit(order.integration, actor, 'order_scanned', order.order_id,
                      product=key, scanned=result['scanned'], required=result['required'], complete=complete)
                return result
            raise ValidationError('Нет необработанного заказа Яндекса, которому ещё нужен этот товар.')
    except IntegrityError:
        event = MarketScanEvent.objects.filter(request_id=request_id).first()
        if event is None:
            raise
        if event.actor_id != actor.pk or event.barcode != barcode:
            raise ValidationError('Идентификатор скана уже использован другим запросом.')
        return event.result


def request_print(*, order, actor, request_id):
    _check_actor(actor)
    if order.fake:
        raise ValidationError('Это тестовый заказ Маркета.')
    with transaction.atomic():
        job, _ = MarketPrintJob.objects.get_or_create(request_id=_uuid(request_id), defaults={
            'order': order, 'actor': actor, 'printer_name': printer_configuration(),
        })
        if job.order_id != order.pk or job.actor_id != actor.pk or job.ready_after_print:
            raise ValidationError('Идентификатор печати уже использован другим запросом.')
        return job


def _save(job, *fields):
    job.save(update_fields=[*fields, 'updated_at'])


def _finished(sync_job):
    if sync_job.state == 'error':
        raise ValidationError(sync_job.last_error or 'Маркет отклонил обработку заказа.')
    return sync_job.state == 'done'


def _step(job):
    _check_actor(job.actor, scanning=job.ready_after_print)
    order = job.order
    if job.ready_after_print:
        if order.fake or not order.integration.enabled or order.sale.is_cancelled or order.sale.is_completed:
            raise ValidationError('Заказ больше недоступен для сборки.')
        if not job.refresh_job_id:
            with transaction.atomic():
                job.refresh_job = request_order_action(order_id=order.pk, actor=job.actor, action='refresh')
                _save(job, 'refresh_job')
            return True
        if not _finished(job.refresh_job):
            return False
        picking = order.picking
        required = required_items(order)
        if required != picking.required or any(picking.scanned.get(key, 0) != count for key, count in required.items()):
            raise ValidationError('Состав заказа изменился или отсканирован не полностью.')
        if order.status != 'PROCESSING' or order.substatus not in ({'STARTED', 'READY_TO_SHIP'} if job.printed_at else {'STARTED'}):
            raise ValidationError('Статус заказа изменился. Автоматическая обработка остановлена.')
        if job.boxes_job_id and not _finished(job.boxes_job):
            return False
        if not order.boxes:
            if job.boxes_job_id:
                raise ValidationError('Маркет не подтвердил создание коробки.')
            boxes = [{'items': [{'id': item['id'], 'fullCount': item['count']} for item in order.items]}]
            with transaction.atomic():
                job.boxes_job = request_order_action(order_id=order.pk, actor=job.actor, action='boxes', boxes=boxes,
                    expected_status=('PROCESSING', 'STARTED'))
                _save(job, 'boxes_job')
            return True
    if not job.document_id:
        with transaction.atomic():
            job.document = request_labels(integration=order.integration, orders=[order], actor=job.actor,
                format_name='A9_HORIZONTALLY', reuse=True)
            job.state = 'waiting_pdf'
            _save(job, 'document', 'state')
        return True
    if job.document.state == 'error':
        raise ValidationError(job.document.last_error or 'Маркет не сформировал PDF стикера.')
    if job.document.state != 'done':
        return False
    if not job.printed_at:
        if job.printer_job_id:
            if job.spooled_at < timezone.now() - timedelta(minutes=3):
                raise ValidationError('Windows не подтвердила печать за три минуты. Проверьте стикер; готовность не отправлена.')
            if not print_job_completed(job.printer_name, job.printer_job_id):
                return False
            with transaction.atomic():
                job.printed_at, job.state = timezone.now(), 'printed'
                _save(job, 'printed_at', 'state')
                audit(order.integration, job.actor, 'label_printed', order.order_id, print_job=job.pk, spool_job=job.printer_job_id)
            try:
                release_print_job(job.printer_name, job.printer_job_id)
            except Exception as exc:
                logger.warning('Не удалось освободить напечатанное задание Windows: print_job=%s error_type=%s', job.pk, type(exc).__name__)
            return True
        with job.document.file.open('rb') as source:
            data = source.read(30 * 1024 * 1024 + 1)
        # Этот маркер фиксируется до внешнего эффекта. После сбоя печать не повторяется автоматически.
        job.state = 'printing'
        _save(job, 'state')
        job.printer_job_id = print_pdf(data, printer_name=job.printer_name, title=f'Yandex order {order.order_id}')
        if not MarketPrintJob.objects.filter(pk=job.pk, lease=job.lease, state='printing').exists():
            raise ValidationError('Результат печати неизвестен после перезапуска процесса. Проверьте стикер.')
        with transaction.atomic():
            job.spooled_at, job.state = timezone.now(), 'spooled'
            _save(job, 'spooled_at', 'printer_job_id', 'state')
            audit(order.integration, job.actor, 'label_spooled', order.order_id, print_job=job.pk, spool_job=job.printer_job_id)
        return True
    if job.ready_after_print:
        if job.ready_job_id:
            if not _finished(job.ready_job):
                return False
        elif order.substatus != 'READY_TO_SHIP':
            with transaction.atomic():
                job.ready_job = request_order_action(order_id=order.pk, actor=job.actor, action='ready',
                    expected_status=('PROCESSING', 'STARTED'))
                job.state = 'waiting_ready'
                _save(job, 'ready_job', 'state')
            return True
    job.state = 'done'
    _save(job, 'state')
    return True


def process_print_jobs(*, limit=50):
    now = timezone.now()
    stale = MarketPrintJob.objects.filter(lease__isnull=False, leased_at__lt=now - timedelta(minutes=3))
    stale.filter(state='printing').update(state='uncertain', last_error='Процесс печати прервался. Проверьте ярлык; автоматического повтора не будет.', lease=None)
    stale.exclude(state='printing').update(lease=None)
    MarketPrintJob.objects.filter(state='printing', lease__isnull=True).update(
        state='uncertain', last_error='Результат прерванной печати неизвестен. Проверьте стикер перед повторением.')
    processed = False
    active = MarketPrintJob.objects.exclude(state__in=['done', 'error', 'uncertain', 'printing']).filter(lease__isnull=True).order_by('pk')
    for pk in list(active.values_list('pk', flat=True)[:limit]):
        lease = uuid.uuid4()
        if not MarketPrintJob.objects.filter(pk=pk, lease__isnull=True).exclude(
                state__in=['done', 'error', 'uncertain']).update(lease=lease, leased_at=now):
            continue
        job = MarketPrintJob.objects.select_related('order__sale', 'order__integration', 'actor', 'document',
            'refresh_job', 'boxes_job', 'ready_job').get(pk=pk, lease=lease)
        try:
            processed = _step(job) or processed
        except OperationalError:
            # Если внешний эффект уже мог произойти, не снимать маркер printing.
            # При недоступной БД аренда истечёт в uncertain, без повторной печати.
            if MarketPrintJob.objects.filter(pk=pk, state='printing').exists():
                raise
        except Exception as exc:
            job.state = 'uncertain' if job.state in {'printing', 'spooled'} else 'error'
            if isinstance(exc, ValidationError):
                job.last_error = ' '.join(exc.messages)
            elif isinstance(exc, PermissionDenied):
                job.last_error = 'Недостаточно прав для печати или готовности заказа.'
            else:
                job.last_error = 'Не удалось обработать печать. Проверьте принтер и заказ.'
            _save(job, 'state', 'last_error')
            processed = True
        finally:
            MarketPrintJob.objects.filter(pk=pk, lease=lease).exclude(state='printing').update(lease=None)
    return processed
