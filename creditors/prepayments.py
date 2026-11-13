"""Атомарный счёт предоплаты партнёра, независимый от знакового долга и кассы."""
import logging
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from cash.services import deposit_cash, deposit_safe
from cash.models import CashTransaction
from core.db_retry import retry_database_lock
from warehouse.models import Warehouse
from .models import Creditor, CreditorTransaction, PrepaymentTransaction
from .services import _debt, adjust_creditor_debt

logger = logging.getLogger("gamebat.business")
ZERO = Decimal("0.00")


def _account(actor, creditor_id):
    if not actor or not actor.is_active or not actor.has_perm("creditors.change_debt"):
        raise PermissionDenied("Нет права изменения счёта предоплаты.")
    try:
        creditor = Creditor.objects.select_for_update().get(pk=creditor_id)
    except Creditor.DoesNotExist as exc:
        raise ValidationError("Счёт партнёра не найден.") from exc
    partner = getattr(creditor, "partner", None)
    if partner is None or partner.is_archived:
        raise ValidationError("Предоплата доступна только действующему партнёру из справочника.")
    return creditor


def _entry(*, creditor, delta, actor, **values):
    old = creditor.prepayment_balance
    new = _debt(old + delta)
    creditor.prepayment_balance = new
    creditor.full_clean()
    creditor.save(update_fields=("prepayment_balance", "updated_at"))
    entry = PrepaymentTransaction(creditor=creditor, old_balance=old, new_balance=new,
        delta=delta, amount=abs(delta), actor=actor, partner_name_snapshot=creditor.partner.name, **values)
    entry.full_clean()
    entry.save()
    logger.info("Предоплата: user_id=%s creditor_id=%s operation_id=%s kind=%s delta=%s balance=%s",
                actor.pk, creditor.pk, entry.pk, entry.kind, delta, new)
    return entry


@retry_database_lock
@transaction.atomic
def fund_prepayment(*, actor, creditor_id, warehouse_id, amount, operation_key,
                    transfer=False, money_source_type="bank", comment=""):
    """Пополняет счёт один раз; перенос долга не создаёт повторного движения денег."""
    creditor = _account(actor, creditor_id)
    amount = _debt(amount)
    if amount <= 0:
        raise ValidationError("Укажите сумму больше нуля.")
    try:
        key = str(uuid.UUID(str(operation_key)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Некорректный ключ операции. Обновите страницу.") from exc
    try:
        warehouse = Warehouse.objects.get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    kind = PrepaymentTransaction.Kind.TRANSFER if transfer else PrepaymentTransaction.Kind.DEPOSIT
    source = "offset" if transfer else money_source_type
    comment = str(comment or "").strip()
    existing = PrepaymentTransaction.objects.filter(operation_key=key).first()
    if existing:
        if (existing.creditor_id, existing.warehouse_id, existing.kind, existing.amount,
                existing.money_source_type, existing.comment) != (creditor.pk, warehouse.pk, kind, amount, source, comment):
            raise ValidationError("Этот ключ уже использован для другой операции. Обновите страницу.")
        return existing
    if CashTransaction.objects.filter(operation_key=key).exists():
        raise ValidationError("Ключ уже использован в денежном журнале. Обновите страницу.")
    cash_entry = debt_entry = None
    if transfer:
        if creditor.current_debt >= 0 or amount > -creditor.current_debt:
            raise ValidationError("Перенести можно только имеющийся отрицательный долг и не больше его суммы.")
        debt_entry = adjust_creditor_debt(actor=actor, creditor_id=creditor.pk, warehouse_id=warehouse.pk,
            debt_delta=amount, money_source_type="offset", comment=comment or "Перенос на отдельный счёт предоплаты")
        debt_entry.kind = CreditorTransaction.Kind.PREPAYMENT_TRANSFER
        debt_entry.save(update_fields=("kind",))
        creditor.refresh_from_db()
    elif source in ("cash", "safe"):
        service = deposit_cash if source == "cash" else deposit_safe
        cash_entry = service(actor=actor, warehouse_id=warehouse.pk, amount=amount, operation_key=key,
            comment=f"Предоплата партнёра «{creditor.display_name}». {comment}".strip())
        # Один кассовый ключ нельзя использовать для двух независимых операций.
        if cash_entry.amount != amount or cash_entry.cash_register.warehouse_id != warehouse.pk:
            raise ValidationError("Денежная операция не соответствует пополнению.")
    elif source != "bank":
        raise ValidationError("Выберите кассу, сейф или банковский перевод.")
    return _entry(creditor=creditor, delta=amount, actor=actor, kind=kind, warehouse=warehouse,
        money_source_type=source, cash_transaction=cash_entry, debt_transaction=debt_entry,
        operation_key=key, comment=comment)


def validate_prepayment_sale(*, actor, partner, sale_type, operation, total, received=None):
    from sales.models import Sale
    if (sale_type != Sale.SaleType.WHOLESALE or partner is None or partner.is_archived or
            operation not in (Sale.OperationKind.NORMAL, Sale.OperationKind.DIGITAL_PRODUCT)):
        raise ValidationError("Счёт предоплаты доступен только в оптовой продаже партнёру из базы.")
    if received not in (None, "") and _debt(received) != 0:
        raise ValidationError("При оплате со счёта предоплаты новые деньги от покупателя не поступают.")
    creditor = _account(actor, partner.creditor_id)
    if total <= 0 or creditor.prepayment_balance < total:
        raise ValidationError(f"Недостаточно предоплаты. Доступно: {creditor.prepayment_balance:.2f} ₽.")
    return creditor


@transaction.atomic
def spend_prepayment(*, sale, actor):
    """Списывает сохранённую стоимость продажи без погашения долга и кассовой проводки."""
    from sales.models import Sale
    if sale.payment_method != Sale.PaymentMethod.PREPAYMENT_ACCOUNT or sale.prepayment_used_amount != sale.total_amount:
        raise ValidationError("В продаже не выбрана оплата со счёта предоплаты.")
    creditor = validate_prepayment_sale(actor=actor, partner=sale.partner, sale_type=sale.sale_type,
        operation=sale.operation_kind, total=sale.total_amount)
    if sale.prepayment_movements.exists():
        raise ValidationError("Предоплата по продаже уже списана.")
    return _entry(creditor=creditor, delta=-sale.total_amount, actor=actor,
        kind=PrepaymentTransaction.Kind.PAYMENT, warehouse=sale.warehouse, money_source_type="offset",
        sale=sale, operation_key=f"sale:{sale.pk}:prepayment", comment=sale.note)


@transaction.atomic
def reverse_prepayment(*, sale, actor, comment):
    """Возвращает только собственное списание продажи; повтор отмены безопасен."""
    original = sale.prepayment_movements.filter(kind=PrepaymentTransaction.Kind.PAYMENT).first()
    if original is None or PrepaymentTransaction.objects.filter(reversal_of=original).exists():
        return
    if original.amount != sale.prepayment_used_amount or original.creditor_id != sale.partner.creditor_id:
        raise ValidationError("Списание предоплаты не соответствует продаже. Проверьте журнал операций.")
    # Архив партнёра не должен блокировать отмену его ранее проведённой продажи.
    if not actor or not actor.has_perm("creditors.change_debt"):
        raise PermissionDenied("Нет права возврата предоплаты.")
    creditor = Creditor.objects.select_for_update().get(pk=original.creditor_id)
    return _entry(creditor=creditor, delta=original.amount, actor=actor,
        kind=PrepaymentTransaction.Kind.REVERSAL, warehouse=sale.warehouse, money_source_type="offset",
        sale=sale, reversal_of=original, operation_key=f"sale:{sale.pk}:prepayment-reversal", comment=comment)
