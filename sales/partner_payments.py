"""Расчёты партнёра через существующий кредиторский журнал, без повторной кассовой проводки."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from creditors.models import Creditor, CreditorTransaction

ZERO, CENT = Decimal('0.00'), Decimal('0.01')
SALT = 'resource.partner-settlement.v1'


def resolve_payment_partner(sale, partner_id):
    """Явный выбор счёта при оплате; текстовое имя не связывает партнёров автоматически."""
    if partner_id in (None, ''):
        return sale.partner
    text = str(partner_id)
    if len(text) > 19 or not text.isascii() or not text.isdecimal() or int(text) <= 0:
        raise ValidationError('Выберите существующего партнёра для расчётов.')
    if sale.partner_id:
        if int(text) != sale.partner_id:
            raise ValidationError('У продажи уже указан другой партнёр. Обновите страницу.')
        return sale.partner
    if not sale.can_select_payment_partner:
        raise ValidationError('Партнёра можно выбрать только при оплате незавершённой оптовой продажи.')
    from partners.models import Partner
    try:
        return Partner.objects.get(pk=int(text), is_archived=False)
    except Partner.DoesNotExist as exc:
        raise ValidationError('Партнёр не найден или находится в архиве.') from exc


def payment_partner_choices():
    from partners.models import Partner
    return Partner.objects.filter(is_archived=False).order_by('name', 'pk').values('id', 'name')


def money(value):
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
        if not amount.is_finite() or amount < 0 or amount >= Decimal('1e18'):
            raise ValueError()
        return amount
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Укажите корректную полученную сумму.') from exc


def quote(*, total, received, debt, partner_id, sale_id=None, creation_key=None):
    debt = Decimal(str(debt)).quantize(CENT)
    total = money(total)
    received = total if received in (None, '') else money(received)
    repayment = min(max(received - total, ZERO), max(debt, ZERO))
    shortfall = max(total - received, ZERO)
    offset = min(shortfall, max(-debt, ZERO))
    charge = shortfall - offset
    return {'partner_id': partner_id, 'sale_id': sale_id, 'creation_key': str(creation_key or ''),
        'total': str(total), 'received': str(received), 'debt_before': str(debt),
        'repayment': str(repayment), 'offset': str(offset), 'charge': str(charge),
        'overpayment': str(max(received - total - repayment, ZERO)),
        'debt_after': str(debt - repayment + offset + charge)}


def payment_values(*, actor, sale_type, partner, total, received, note, confirmation='', sale_id=None, creation_key=None):
    from .models import Sale
    actual = total if received in (None, '') else money(received)
    if sale_type != Sale.SaleType.WHOLESALE or partner is None:
        if actual < total:
            if sale_type == Sale.SaleType.WHOLESALE and partner is None:
                raise ValidationError('Для частичной оплаты выберите партнёра из справочника.')
            raise ValidationError('Полученная сумма не может быть меньше стоимости продажи.')
        return actual, max(actual - total, ZERO), ZERO, ZERO
    creditor = Creditor.objects.select_for_update().get(pk=partner.creditor_id)
    values = quote(total=total, received=actual, debt=creditor.current_debt, partner_id=partner.pk,
        sale_id=sale_id, creation_key=creation_key)
    repayment, offset = Decimal(values['repayment']), Decimal(values['offset'])
    if repayment or offset or Decimal(values['charge']):
        if actor is None or not actor.has_perm('creditors.change_debt'):
            raise PermissionDenied('Нет права изменения задолженности.')
        if not str(note or '').strip():
            raise ValidationError('Для расчёта задолженности обязательно укажите примечание.')
        try:
            confirmed = signing.loads(confirmation, salt=SALT, max_age=600)
        except (signing.BadSignature, TypeError) as exc:
            raise ValidationError('Подтвердите расчёт задолженности перед сохранением.') from exc
        if confirmed != values:
            raise ValidationError('Сумма или задолженность изменились. Проверьте и подтвердите расчёт заново.')
    return actual, Decimal(values['overpayment']), repayment, offset


@transaction.atomic
def record_settlement(*, sale, actor):
    charge = sale.debt_charge_amount
    amount = sale.debt_repayment_amount or sale.debt_offset_amount + charge
    if not amount:
        return
    if actor is None or not actor.has_perm('creditors.change_debt'):
        raise PermissionDenied('Нет права изменения задолженности.')
    creditor = Creditor.objects.select_for_update().get(pk=sale.partner.creditor_id)
    key = f'sale:{sale.pk}:settlement'
    if CreditorTransaction.objects.filter(operation_key=key).exists():
        raise ValidationError('Расчёт по продаже уже проведён.')
    old = creditor.current_debt
    repayment = sale.debt_repayment_amount > 0
    if not sale.is_partner_debt and ((repayment and old < amount) or (not repayment and not charge and -old < amount)):
        raise ValidationError('Задолженность изменилась. Подтвердите расчёт заново.')
    creditor.current_debt = old - amount if repayment else old + amount
    creditor.full_clean()
    creditor.save(update_fields=('current_debt', 'updated_at'))
    CreditorTransaction.objects.create(creditor=creditor, sale=sale, operation_key=key,
        kind=(CreditorTransaction.Kind.SALE_DEBT if charge else
            CreditorTransaction.Kind.REPAYMENT if repayment else CreditorTransaction.Kind.OFFSET),
        partner_name_snapshot=sale.partner_name_snapshot, old_debt=old, new_debt=creditor.current_debt,
        delta=creditor.current_debt - old, amount=amount, warehouse=sale.warehouse,
        money_source_type=CreditorTransaction.MoneySourceType.OFFSET,
        actor=actor, comment=sale.note)


@transaction.atomic
def reverse_settlement(*, sale, actor, comment):
    original = sale.creditor_movements.filter(reversal_of__isnull=True).first()
    if not original or CreditorTransaction.objects.filter(reversal_of=original).exists():
        return
    if not actor.has_perm('creditors.change_debt'):
        raise PermissionDenied('Для отмены расчёта требуется право изменения задолженности.')
    creditor = Creditor.objects.select_for_update().get(pk=original.creditor_id)
    old = creditor.current_debt
    creditor.current_debt -= original.delta
    creditor.save(update_fields=('current_debt', 'updated_at'))
    CreditorTransaction.objects.create(creditor=creditor, sale=sale, operation_key=f'sale:{sale.pk}:reversal',
        reversal_of=original, kind=CreditorTransaction.Kind.REVERSAL,
        partner_name_snapshot=original.partner_name_snapshot, old_debt=old, new_debt=creditor.current_debt,
        delta=-original.delta, amount=original.amount, warehouse=sale.warehouse,
        money_source_type=CreditorTransaction.MoneySourceType.OFFSET, actor=actor, comment=comment)
