"""Безопасные операции с физическими наличными касс складов."""
import logging
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CashRegister, CashTransaction, Safe

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


def _operation_key(value):
    if value in (None, ""):
        return uuid.uuid4()
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Некорректный ключ денежной операции.") from exc


def _existing_operation(operation_key, operation_type):
    operation = CashTransaction.objects.select_for_update().filter(operation_key=operation_key).first()
    if operation is None:
        return None
    if operation.operation_type != operation_type:
        raise ValidationError("Этот ключ уже использован для другой денежной операции.")
    return operation


def _locked_register(warehouse_id):
    try:
        return CashRegister.objects.select_for_update().select_related("warehouse").get(warehouse_id=warehouse_id)
    except CashRegister.DoesNotExist as exc:
        raise ValidationError("Для выбранного склада не создана касса.") from exc


def _locked_safe(warehouse_id):
    try:
        return Safe.objects.select_for_update().select_related("warehouse").get(warehouse_id=warehouse_id)
    except Safe.DoesNotExist as exc:
        raise ValidationError("Для выбранного склада не создан сейф.") from exc


@transaction.atomic
def deposit_cash(*, actor, warehouse_id, amount, comment, operation_key=None):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    operation_key = _operation_key(operation_key)
    existing = _existing_operation(operation_key, CashTransaction.OperationType.DEPOSIT)
    if existing:
        return existing
    register = _locked_register(warehouse_id)
    register.balance += amount
    register.full_clean()
    register.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, operation_type=CashTransaction.OperationType.DEPOSIT,
        amount=amount, comment=comment, created_by=actor, operation_key=operation_key,
    )
    logger.info(
        "Наличные внесены: user_id=%s register_id=%s transaction_id=%s amount=%s",
        actor.pk, register.pk, operation.pk, amount,
    )
    return operation


@transaction.atomic
def collect_cash(*, actor, warehouse_id, amount, comment, operation_key=None):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    operation_key = _operation_key(operation_key)
    existing = _existing_operation(operation_key, CashTransaction.OperationType.COLLECTION)
    if existing:
        return existing
    register = _locked_register(warehouse_id)
    if register.balance < amount:
        raise ValidationError("Недостаточно наличных для инкассации.")
    register.balance -= amount
    register.full_clean()
    register.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, operation_type=CashTransaction.OperationType.COLLECTION,
        amount=amount, comment=comment, created_by=actor, operation_key=operation_key,
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


@transaction.atomic
def deposit_safe(*, actor, warehouse_id, amount, comment, operation_key=None):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    operation_key = _operation_key(operation_key)
    existing = _existing_operation(operation_key, CashTransaction.OperationType.SAFE_DEPOSIT)
    if existing:
        return existing
    safe = _locked_safe(warehouse_id)
    register = CashRegister.objects.get(warehouse_id=warehouse_id)
    safe.balance += amount
    safe.full_clean()
    safe.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, safe=safe,
        operation_type=CashTransaction.OperationType.SAFE_DEPOSIT,
        amount=amount, comment=comment, created_by=actor, operation_key=operation_key,
    )
    logger.info(
        "Наличные внесены в сейф: user_id=%s warehouse_id=%s safe_id=%s transaction_id=%s amount=%s",
        actor.pk, warehouse_id, safe.pk, operation.pk, amount,
    )
    return operation


@transaction.atomic
def collect_safe(*, actor, warehouse_id, amount, comment, operation_key=None):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    operation_key = _operation_key(operation_key)
    existing = _existing_operation(operation_key, CashTransaction.OperationType.SAFE_COLLECTION)
    if existing:
        return existing
    safe = _locked_safe(warehouse_id)
    if safe.balance < amount:
        raise ValidationError("Недостаточно наличных в сейфе для инкассации.")
    register = CashRegister.objects.get(warehouse_id=warehouse_id)
    safe.balance -= amount
    safe.full_clean()
    safe.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, safe=safe,
        operation_type=CashTransaction.OperationType.SAFE_COLLECTION,
        amount=amount, comment=comment, created_by=actor, operation_key=operation_key,
    )
    logger.info(
        "Наличные инкассированы из сейфа: user_id=%s warehouse_id=%s safe_id=%s transaction_id=%s amount=%s",
        actor.pk, warehouse_id, safe.pk, operation.pk, amount,
    )
    return operation


@transaction.atomic
def transfer_cash_to_safe(*, actor, warehouse_id, amount, comment, operation_key=None):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    operation_key = _operation_key(operation_key)
    existing = _existing_operation(operation_key, CashTransaction.OperationType.CASH_TO_SAFE)
    if existing:
        return existing
    register = _locked_register(warehouse_id)
    safe = _locked_safe(warehouse_id)
    if register.balance < amount:
        raise ValidationError("Недостаточно наличных в кассе для перевода.")
    register.balance -= amount
    safe.balance += amount
    register.full_clean()
    safe.full_clean()
    register.save(update_fields=("balance",))
    safe.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, safe=safe,
        operation_type=CashTransaction.OperationType.CASH_TO_SAFE,
        amount=amount, comment=comment, created_by=actor, operation_key=operation_key,
    )
    logger.info(
        "Наличные переведены из кассы в сейф: user_id=%s warehouse_id=%s transaction_id=%s amount=%s",
        actor.pk, warehouse_id, operation.pk, amount,
    )
    return operation


@transaction.atomic
def transfer_safe_to_cash(*, actor, warehouse_id, amount, comment, operation_key=None):
    amount = _positive_amount(amount)
    comment = _comment(comment)
    operation_key = _operation_key(operation_key)
    existing = _existing_operation(operation_key, CashTransaction.OperationType.SAFE_TO_CASH)
    if existing:
        return existing
    register = _locked_register(warehouse_id)
    safe = _locked_safe(warehouse_id)
    if safe.balance < amount:
        raise ValidationError("Недостаточно наличных в сейфе для перевода.")
    safe.balance -= amount
    register.balance += amount
    safe.full_clean()
    register.full_clean()
    safe.save(update_fields=("balance",))
    register.save(update_fields=("balance",))
    operation = CashTransaction.objects.create(
        cash_register=register, safe=safe,
        operation_type=CashTransaction.OperationType.SAFE_TO_CASH,
        amount=amount, comment=comment, created_by=actor, operation_key=operation_key,
    )
    logger.info(
        "Наличные переведены из сейфа в кассу: user_id=%s warehouse_id=%s transaction_id=%s amount=%s",
        actor.pk, warehouse_id, operation.pk, amount,
    )
    return operation
