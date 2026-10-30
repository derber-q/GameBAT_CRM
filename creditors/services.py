"""Атомарные расчёты с кредиторами через существующие кассу и сейф."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from cash.models import CashRegister, CashTransaction, Safe
from warehouse.models import Warehouse
from .models import Creditor, CreditorTransaction
from core.db_retry import retry_database_lock

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")


def _debt(value, *, signed=False):
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную сумму задолженности.") from exc
    if not result.is_finite() or abs(result) >= Decimal('1e18'):
        raise ValidationError('Укажите корректную сумму задолженности.')
    if result < 0 and not signed:
        raise ValidationError("Задолженность не может быть отрицательной.")
    return result


@retry_database_lock
@transaction.atomic
def adjust_creditor_debt(*, actor, creditor_id, warehouse_id, money_source_type, new_debt=None, debt_delta=None, comment=""):
    if not actor.has_perm('creditors.change_debt'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Нет права изменения задолженности.')
    if (new_debt is None) == (debt_delta is None):
        raise ValidationError('Укажите итоговую задолженность или сумму изменения.')
    try:
        creditor = Creditor.objects.select_for_update().get(pk=creditor_id)
    except Creditor.DoesNotExist as exc:
        raise ValidationError("Кредитор не найден.") from exc
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc

    partner = getattr(creditor, 'partner', None)
    old_debt = creditor.current_debt
    # При относительном изменении используем баланс под блокировкой, а не
    # значение страницы: другая операция могла изменить долг после её открытия.
    if debt_delta is not None:
        new_debt = old_debt + _debt(debt_delta, signed=True)
    new_debt = _debt(new_debt, signed=partner is not None)
    delta = (new_debt - old_debt).quantize(CENT)
    if delta == 0:
        raise ValidationError("Новое значение задолженности совпадает с текущим.")
    amount = abs(delta)

    try:
        register = CashRegister.objects.select_for_update().get(warehouse=warehouse)
    except CashRegister.DoesNotExist as exc:
        raise ValidationError("Для выбранного склада не создана касса.") from exc

    if money_source_type == CreditorTransaction.MoneySourceType.CASH:
        storage = register
        safe = None
        insufficient_message = "Недостаточно средств в выбранной кассе."
    elif money_source_type == CreditorTransaction.MoneySourceType.SAFE:
        try:
            storage = Safe.objects.select_for_update().get(warehouse=warehouse)
        except Safe.DoesNotExist as exc:
            raise ValidationError("Для выбранного склада не создан сейф.") from exc
        safe = storage
        insufficient_message = "Недостаточно средств в выбранном сейфе."
    elif money_source_type in (CreditorTransaction.MoneySourceType.BANK, CreditorTransaction.MoneySourceType.OFFSET):
        storage, safe = None, None
        if not str(comment or '').strip():
            raise ValidationError('Для банковской или безденежной операции укажите комментарий.')
    else:
        raise ValidationError("Выберите кассу или сейф.")

    increasing = delta > 0
    if storage is not None and increasing and storage.balance < amount:
        raise ValidationError(insufficient_message)
    if storage is not None:
        storage.balance = storage.balance - amount if increasing else storage.balance + amount
        storage.full_clean()
        storage.save(update_fields=("balance",))

    creditor.current_debt = new_debt
    creditor.full_clean()
    creditor.save(update_fields=("current_debt", "updated_at"))
    operation_type = (
        CashTransaction.OperationType.CREDITOR_ADVANCE
        if increasing else CashTransaction.OperationType.CREDITOR_REPAYMENT
    )
    action = "Увеличение задолженности" if increasing else "Погашение задолженности"
    cash_transaction = CashTransaction.objects.create(
        cash_register=register, safe=safe, operation_type=operation_type, amount=amount,
        comment=f"Кредитор «{creditor.name}». {action}. {str(comment or '').strip()}".strip(),
        created_by=actor,
    ) if storage is not None else None
    creditor_transaction = CreditorTransaction.objects.create(
        creditor=creditor, old_debt=old_debt, new_debt=new_debt, delta=delta,
        warehouse=warehouse, money_source_type=money_source_type, amount=amount,
        cash_transaction=cash_transaction, actor=actor, comment=str(comment or "").strip(),
        partner_name_snapshot=partner.name if partner else '',
    )
    logger.info(
        "Операция кредитора проведена: user_id=%s creditor_id=%s warehouse_id=%s "
        "storage=%s old_debt=%s new_debt=%s amount=%s",
        actor.pk, creditor.pk, warehouse.pk, money_source_type, old_debt, new_debt, amount,
    )
    return creditor_transaction
