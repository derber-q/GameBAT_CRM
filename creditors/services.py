"""Атомарные расчёты с кредиторами через существующие кассу и сейф."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from cash.models import CashRegister, CashTransaction, Safe
from warehouse.models import Warehouse
from .models import Creditor, CreditorTransaction

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")


def _debt(value):
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную сумму задолженности.") from exc
    if result < 0:
        raise ValidationError("Задолженность не может быть отрицательной.")
    return result


@transaction.atomic
def adjust_creditor_debt(*, actor, creditor_id, warehouse_id, money_source_type, new_debt, comment=""):
    try:
        creditor = Creditor.objects.select_for_update().get(pk=creditor_id)
    except Creditor.DoesNotExist as exc:
        raise ValidationError("Кредитор не найден.") from exc
    try:
        warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc

    new_debt = _debt(new_debt)
    old_debt = creditor.current_debt
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
    else:
        raise ValidationError("Выберите кассу или сейф.")

    increasing = delta > 0
    if increasing and storage.balance < amount:
        raise ValidationError(insufficient_message)
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
    )
    creditor_transaction = CreditorTransaction.objects.create(
        creditor=creditor, old_debt=old_debt, new_debt=new_debt, delta=delta,
        warehouse=warehouse, money_source_type=money_source_type, amount=amount,
        cash_transaction=cash_transaction, actor=actor, comment=str(comment or "").strip(),
    )
    logger.info(
        "Операция кредитора проведена: user_id=%s creditor_id=%s warehouse_id=%s "
        "storage=%s old_debt=%s new_debt=%s amount=%s",
        actor.pk, creditor.pk, warehouse.pk, money_source_type, old_debt, new_debt, amount,
    )
    return creditor_transaction
