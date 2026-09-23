"""Подписанные снимки партий и защита штатных операций от повторной отправки."""
from uuid import uuid4
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import CDConsignmentStock, TechConsignmentStock, ConsignmentActionReceipt
from .services import return_from_consignment, record_consignment_sale

SALT = 'consignment.row.action.v1'


def stock_queryset(kind):
    if kind == 'cd':
        return CDConsignmentStock.objects.select_related('cd__platform', 'warehouse', 'platform')
    if kind == 'tech':
        return TechConsignmentStock.objects.select_related('tech__product_type', 'warehouse', 'platform')
    raise ValidationError('Неизвестный тип товара.')


def action_token(stock, kind, user):
    return signing.dumps({
        'key': str(uuid4()), 'user': user.pk, 'kind': kind, 'stock': stock.pk,
        'quantity': stock.quantity, 'reward': str(stock.receivable_per_unit),
    }, salt=SALT)


@transaction.atomic
def perform_row_action(*, actor, kind, stock_id, token, action, quantity,
                       warehouse_id=None, payment_method=None):
    try:
        snapshot = signing.loads(token, salt=SALT, max_age=86400)
    except signing.BadSignature as exc:
        raise ValidationError('Данные строки устарели. Обновите список и повторите действие.') from exc
    if (snapshot['user'], snapshot['kind'], snapshot['stock']) != (actor.pk, kind, stock_id):
        raise ValidationError('Подтверждение относится к другой строке или пользователю.')
    if action not in ('return', 'sold'):
        raise ValidationError('Неизвестная операция.')
    # Первая запись сериализует пишущие транзакции и в SQLite, где нет обычных
    # построчных блокировок SELECT FOR UPDATE. Повторный ключ вызывает откат;
    # квитанция и изменение остатка должны оставаться в одной транзакции.
    ConsignmentActionReceipt.objects.create(
        key=snapshot['key'], created_by=actor, product_kind=kind, stock_id=stock_id, action=action,
    )
    stock = stock_queryset(kind).select_for_update().filter(pk=stock_id).first()
    if stock is None:
        raise ValidationError('Позиция на реализации не найдена.')
    product = stock.cd if kind == 'cd' else stock.tech
    if product.is_archived:
        raise ValidationError('Товар находится в архиве.')
    if stock.quantity != snapshot['quantity'] or str(stock.receivable_per_unit) != snapshot['reward']:
        raise ValidationError('Количество или вознаграждение уже изменились. Проверьте обновлённую строку и подтвердите заново.')
    if action == 'return':
        if not warehouse_id:
            raise ValidationError('Выберите склад возврата.')
        return return_from_consignment(
            actor=actor, warehouse_id=stock.warehouse_id, target_warehouse_id=warehouse_id,
            platform_id=stock.platform_id, product_type=kind, product_id=product.pk,
            stock_id=stock.pk, quantity=quantity,
        )
    return record_consignment_sale(
        actor=actor, product_type=kind, stock_id=stock.pk, quantity=quantity, payment_method=payment_method,
    )
