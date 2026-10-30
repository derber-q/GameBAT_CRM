"""Отметки и защита редактирования на странице рейса; учётные сервисы их не читают."""
import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SupplierOrderBatch, SupplierOrderBatchLine, SupplierTripInvoice
from .trips import _require_manage

logger = logging.getLogger('gamebat.business')


def _locked_batch(batch_id):
    try:
        return SupplierOrderBatch.objects.trips().select_for_update().get(pk=batch_id)
    except SupplierOrderBatch.DoesNotExist as exc:
        raise ValidationError('Рейс не найден.') from exc


@transaction.atomic
def set_invoice_accepted(*, actor, batch_id, supplier_id, accepted):
    _require_manage(actor)
    batch = _locked_batch(batch_id)
    if not isinstance(accepted, bool):
        raise ValidationError('Укажите состояние флага инвойса.')
    if not batch.lines.filter(supplier_id=supplier_id).exists():
        raise ValidationError('Этот поставщик отсутствует в рейсе.')
    flag, created = SupplierTripInvoice.objects.get_or_create(batch=batch, supplier_id=supplier_id,
        defaults={'accepted': accepted, 'updated_by': actor})
    if not created and flag.accepted != accepted:
        flag.accepted, flag.updated_by = accepted, actor
        flag.save(update_fields=('accepted', 'updated_by', 'updated_at'))
    logger.info('Отметка инвойса рейса: user_id=%s batch_id=%s supplier_id=%s accepted=%s',
        actor.pk, batch.pk, supplier_id, accepted)
    return flag


def require_page_editable(*, batch_id, line_id, target_supplier_id=None, returning_to_m=False):
    """Вызывается внутри транзакции HTTP-обработчика; блокировка общая с переключателем."""
    batch = _locked_batch(batch_id)
    try:
        line = SupplierOrderBatchLine.objects.get(pk=line_id, batch=batch)
    except SupplierOrderBatchLine.DoesNotExist as exc:
        raise ValidationError('Строка рейса не найдена.') from exc
    supplier_ids = {line.supplier_id}
    if returning_to_m:
        supplier_ids.add(line.price_supplier_id)
    elif str(target_supplier_id or '').isdecimal():
        supplier_ids.add(int(target_supplier_id))
    if batch.invoice_flags.filter(supplier_id__in=supplier_ids, accepted=True).exists():
        raise ValidationError('Инвойс поставщика принят. Снимите флаг «Инвойс принят» на странице рейса перед редактированием.')
