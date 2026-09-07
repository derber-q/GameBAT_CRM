"""Безопасные операции с физическими наличными касс складов."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CashRegister, CashTransaction

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")


def _positive_amount(value):
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную сумму.") from exc
    if amount <= 0:
        raise ValidationError("Сумма должна быть больше нуля.")
    return amount


def _comment(value):
    result = str(value or "").strip()
    if not result:
        raise ValidationError("Комментарий обязателен.")
    return result


def _locked_register(warehouse_id):
    try:
        return CashRegister.objects.select_for_update().select_related("warehouse").get(warehouse_id=warehouse_id)
    except CashRegister.DoesNotExist as exc:
        raise ValidationError("Для выбранного склада не создана касса.") from exc


@transaction.atomic
def deposit_cash(*, actor, warehouse_id, amount, comment):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    register = _locked_register(warehouse_id)
    register.balance += amount
    register.full_clean()
    register.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, operation_type=CashTransaction.OperationType.DEPOSIT,
        amount=amount, comment=comment, created_by=actor,
    )
    logger.info(
        "Наличные внесены: user_id=%s register_id=%s transaction_id=%s amount=%s",
        actor.pk, register.pk, operation.pk, amount,
    )
    return operation


@transaction.atomic
def collect_cash(*, actor, warehouse_id, amount, comment):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    register = _locked_register(warehouse_id)
    if register.balance < amount:
        raise ValidationError("Недостаточно наличных для инкассации.")
    register.balance -= amount
    register.full_clean()
    register.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, operation_type=CashTransaction.OperationType.COLLECTION,
        amount=amount, comment=comment, created_by=actor,
    )
    logger.info(
        "Наличные инкассированы: user_id=%s register_id=%s transaction_id=%s amount=%s",
        actor.pk, register.pk, operation.pk, amount,
    )
    return operation


@transaction.atomic
def credit_sale_payment(*, sale, actor):
    """Зачисляет оплату продажи ровно один раз в кассу её склада."""
    register = _locked_register(sale.warehouse_id)
    if CashTransaction.objects.select_for_update().filter(sale=sale).exists():
        raise ValidationError("Оплата этой продажи уже проведена.")
    register.balance += sale.total_amount
    register.full_clean()
    register.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register,
        operation_type=CashTransaction.OperationType.SALE_PAYMENT,
        amount=sale.total_amount,
        comment=f"Продажа {sale.visible_id}.",
        created_by=actor,
        sale=sale,
    )
    logger.info(
        "Наличная оплата продажи: user_id=%s sale_id=%s transaction_id=%s amount=%s",
        actor.pk, sale.pk, operation.pk, sale.total_amount,
    )
    return operation
