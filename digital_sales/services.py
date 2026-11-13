"""Атомарный цифровой учёт поверх Sale: без физических запасов и кассовых проводок."""
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from sales.models import Sale, SaleCustomItem
from .models import Buyer, Supplier, DigitalOrder, OrderReference, BalanceMovement, AuditEvent
from .parser import money

ZERO = Decimal('0.00')


def record_id(value):
    text = str(value or '')
    if not text.isascii() or not text.isdecimal() or len(text) > 19 or not 0 < int(text) < 2**63:
        raise ValidationError('Укажите корректный числовой идентификатор записи.')
    return int(text)


def require(actor, *permissions):
    """Каждый вход проверяет свежие права: старые callback и кэш User не дают доступ."""
    current = get_user_model().objects.filter(pk=getattr(actor, 'pk', None), is_active=True).first()
    if not current or not current.has_perms(permissions):
        raise PermissionDenied('Недостаточно прав для цифровой операции.')
    return current


def _key(value):
    try:
        return uuid.UUID(str(value)) if value else uuid.uuid4()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Некорректный ключ операции.') from None


@retry_database_lock
@transaction.atomic
def move_balance(*, actor, amount, kind, reason, buyer_id=None, supplier_id=None, operation_key=None):
    actor = require(actor, 'digital_sales.topup_digital_balances' if kind == 'topup' else 'digital_sales.adjust_digital_balances')
    if bool(buyer_id) == bool(supplier_id) or kind not in ('opening', 'topup', 'adjustment'):
        raise ValidationError('Выберите один счёт и допустимый вид движения.')
    amount = money(amount)
    reason = str(reason or '').strip()
    if not amount or (kind == 'topup' and amount < 0) or not 1 <= len(reason) <= 500:
        raise ValidationError('Укажите ненулевую сумму и причину; пополнение не может быть отрицательным.')
    owner = (Buyer if buyer_id else Supplier).objects.select_for_update().get(pk=buyer_id or supplier_id)
    key = _key(operation_key)
    old = BalanceMovement.objects.filter(operation_key=key).first()
    if old:
        if (old.buyer_id != (owner.pk if buyer_id else None) or old.supplier_id != (owner.pk if supplier_id else None)
                or old.delta != amount or old.kind != kind or old.reason != reason):
            raise ValidationError('Ключ уже использован для другого движения.')
        return old
    if kind == 'opening' and owner.movements.exists():
        raise ValidationError('Начальный остаток уже задан; используйте корректировку.')
    # Начальный долг и корректировки допустимы для обоих счетов; пополнение — положительное движение.
    movement = BalanceMovement.objects.create(buyer_id=buyer_id, supplier_id=supplier_id, delta=amount,
                    kind=kind, reason=reason, actor=actor, operation_key=key)
    if buyer_id:
        owner.save(update_fields=['updated_at'])
        from .chat_balances import enqueue_balance
        enqueue_balance(owner, event=f'balance:{movement.pk}')
    AuditEvent.objects.create(actor=actor, kind='balance_' + kind, detail=f'movement={movement.pk}')
    return movement


def normalized_items(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValidationError('Добавьте от одной до ста цифровых позиций.')
    rows = []
    for row in items:
        if not isinstance(row, dict):
            raise ValidationError('Неверный формат позиции.')
        name = str(row.get('name', '')).strip()
        cost = money(row.get('cost'))
        number = str(row.get('number') or '').strip().lstrip('#')
        if not 1 <= len(name) <= 255 or cost < 0:
            raise ValidationError('Проверьте название и неотрицательную себестоимость.')
        if number and (not number.isascii() or not number.isdecimal() or len(number) > 20):
            raise ValidationError('Номер поставщика должен состоять из цифр.')
        rows.append({'name': name, 'cost': str(cost), 'number': number})
    if sum((money(row['cost']) for row in rows), ZERO) >= Decimal('1e18'):
        raise ValidationError('Общая себестоимость слишком велика.')
    return rows


def allocate_price(total, costs):
    """Распределение копеек: целая часть доли, затем наибольшие остатки и индекс."""
    cents = int(money(total) * 100)
    weights = [int(money(cost) * 100) for cost in costs]
    if not weights:
        raise ValidationError('Пустой состав продажи.')
    if not sum(weights):
        weights = [1] * len(weights)
    weight = sum(weights)
    amounts = [cents * value // weight for value in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(cents * weights[i] % weight), i))
    for index in order[:cents - sum(amounts)]:
        amounts[index] += 1
    return [Decimal(value) / 100 for value in amounts]


def _version(order, revision):
    if order.processing_stopped:
        raise ValidationError('Заказ отменён и исключён из обработки.')
    if str(order.revision) != str(revision):
        raise ValidationError('Заказ уже изменён другим сотрудником. Откройте актуальную карточку.')


@retry_database_lock
@transaction.atomic
def ignore_incoming_order(*, actor, order_id, revision):
    """Исключение входящего заказа не означает возврат денег поставщиком."""
    actor = require(actor, 'digital_sales.telegram_digital_sales', 'digital_sales.cancel_digital_sales')
    source = DigitalOrder.objects.get(pk=order_id)
    Supplier.objects.select_for_update().get(pk=source.supplier_id)
    order = DigitalOrder.objects.select_for_update().get(pk=source.pk)
    if order.ignored_at:
        return order
    _version(order, revision)
    if order.sale_id:
        raise ValidationError('Продажа уже создана. Используйте штатную отмену продажи в CRM.')
    order.ignored_at, order.ignored_by = timezone.now(), actor
    order.state, order.revision = DigitalOrder.State.CANCELLED, order.revision + 1
    order.save(update_fields=['ignored_at', 'ignored_by', 'state', 'revision', 'updated_at'])
    from .models import StaffConversation, SupplierMessage, Notification
    StaffConversation.objects.filter(order=order).delete()
    for message in SupplierMessage.objects.filter(order=order, attachment_state__in=['pending', 'error']):
        message.attachment_state = 'ignored'
        message.save(update_fields=['attachment_state'])
    for notice in Notification.objects.filter(order=order, state='queued'):
        notice.state = 'revoked'
        notice.save(update_fields=['state'])
    AuditEvent.objects.create(order=order, actor=actor, kind='incoming_order_ignored',
        detail='Исключён из обработки через Telegram; подтверждённый расход поставщика сохранён')
    from .notifications import enqueue_order
    enqueue_order(order, event=f'ignored:{order.revision}')
    return order


@retry_database_lock
@transaction.atomic
def save_draft(*, actor, order_id, revision, buyer_id, price, is_retail=False):
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    order = DigitalOrder.objects.select_for_update().get(pk=order_id)
    _version(order, revision)
    if order.sale_id:
        raise ValidationError('Продажа уже создана; общий черновик закрыт.')
    if is_retail and buyer_id:
        raise ValidationError('Розничная продажа не использует счёт покупателя.')
    order.buyer = Buyer.objects.get(pk=buyer_id) if buyer_id else None
    order.is_retail = bool(is_retail)
    order.price = money(price, positive=True)
    order.revision += 1
    order.edited_by = actor
    order.save(update_fields=['buyer', 'is_retail', 'price', 'revision', 'edited_by', 'updated_at'])
    AuditEvent.objects.create(order=order, actor=actor, kind='draft_saved', detail=f'revision={order.revision}')
    return order


@retry_database_lock
@transaction.atomic
def select_buyer(*, actor, order_id, revision, buyer_id=None, is_retail=False):
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    order = DigitalOrder.objects.select_for_update().get(pk=order_id)
    _version(order, revision)
    if order.sale_id or bool(buyer_id) == bool(is_retail):
        raise ValidationError('Выберите покупателя из базы или розничный вариант до создания продажи.')
    order.buyer = None if is_retail else Buyer.objects.get(pk=buyer_id)
    order.is_retail, order.edited_by, order.revision = bool(is_retail), actor, order.revision + 1
    order.save(update_fields=['buyer', 'is_retail', 'edited_by', 'revision', 'updated_at'])
    AuditEvent.objects.create(order=order, actor=actor, kind='buyer_selected',
                             detail='retail' if is_retail else f'buyer={buyer_id}')
    return order


@retry_database_lock
@transaction.atomic
def confirm_order(*, actor, order_id, revision, complete_immediately=False):
    """Telegram явно запрашивает полное проведение; веб сохраняет прежний сценарий."""
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    order = DigitalOrder.objects.select_for_update().select_related('buyer').get(pk=order_id)
    if order.sale_id:
        return order.sale
    _version(order, revision)
    if order.state != DigitalOrder.State.READY or not order.checklist_received or not order.goods_received or order.review_reason:
        raise ValidationError('Сначала проверьте чек-лист и готовность цифрового товара.')
    if (not order.buyer_id and not order.is_retail) or order.price is None:
        raise ValidationError('Выберите покупателя и сохраните общую цену.')
    if order.is_retail or complete_immediately:
        # Права проверяются до создания Sale, чтобы не оставить частично оформленную продажу.
        require(actor, 'digital_sales.complete_digital_sales', 'sales.mark_sale_paid')
    from catalog.models import SystemProduct
    if not SystemProduct.objects.filter(kind=SystemProduct.Kind.DIGITAL_PRODUCT).exists():
        raise ValidationError('Системная позиция цифрового товара не установлена. Проверьте миграции каталога.')
    rows = normalized_items(order.items)
    if sum((money(row['cost']) for row in rows), ZERO) != order.cost:
        raise ValidationError('Себестоимость состава не совпадает с итогом.')
    sale = Sale.objects.create(sale_type=Sale.SaleType.DIGITAL, operation_kind=Sale.OperationKind.DIGITAL_PRODUCT,
        warehouse=None, price_type=Sale.PriceType.RETAIL, payment_method=Sale.PaymentMethod.BANK_CARD,
        order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.UNPAID,
        total_amount=money(order.price, positive=True), created_by=actor, creation_key=order.creation_key,
        note=f'Цифровой заказ №{order.pk}', partner=None if order.is_retail else order.buyer.partner,
        partner_name_snapshot=order.customer_display_name)
    sale.visible_id = f'SALE-{sale.pk:06d}'
    sale.full_clean()
    sale.save(update_fields=['visible_id'])
    for row, price in zip(rows, allocate_price(order.price, [money(row['cost']) for row in rows]), strict=True):
        item = SaleCustomItem(sale=sale, system_product_id=Sale.OperationKind.DIGITAL_PRODUCT,
            product_name_snapshot=row['name'], article_snapshot=row['number'], quantity=1,
            unit_price=price, line_total=price, unit_cost_snapshot=money(row['cost']))
        item.full_clean()
        item.save()
    order.sale, order.state = sale, DigitalOrder.State.SALE
    order.confirmed_by, order.confirmed_at = actor, timezone.now()
    order.revision += 1
    order.save(update_fields=['sale', 'state', 'confirmed_by', 'confirmed_at', 'revision', 'updated_at'])
    AuditEvent.objects.create(order=order, actor=actor, kind='sale_created', detail=f'sale={sale.pk}')
    if order.is_retail or complete_immediately:
        return complete_sale(actor=actor, sale_id=sale.pk)
    from .notifications import enqueue_order
    enqueue_order(order, event=f'confirmed:{order.revision}')
    return sale


@retry_database_lock
@transaction.atomic
def manual_sale(*, actor, supplier_id, buyer_id, items, price, creation_key, numbers=(), secret='', comment='', source_url='', is_retail=False):
    actor = require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale')
    supplier = Supplier.objects.select_for_update().get(pk=supplier_id)
    rows, total = normalized_items(items), money(price, positive=True)
    key = _key(creation_key)
    existing = DigitalOrder.objects.filter(creation_key=key).first()
    if existing:
        if (existing.items != rows or existing.price != total or existing.buyer_id != (int(buyer_id) if buyer_id else None)
                or existing.is_retail != bool(is_retail)
                or existing.supplier_id != supplier.pk):
            raise ValidationError('Форма уже использована с другими данными.')
        return existing.sale
    numbers = sorted(set(str(value).strip().lstrip('#') for value in [*numbers, *(row['number'] for row in rows)] if str(value).strip()))
    if any(not value.isascii() or not value.isdecimal() or len(value) > 20 for value in numbers):
        raise ValidationError('Номера поставщика должны состоять из цифр.')
    if OrderReference.objects.filter(supplier=supplier, number__in=numbers).exists():
        raise ValidationError('Номер уже связан с цифровым заказом. Откройте существующую запись или свяжите сообщения вручную.')
    if bool(buyer_id) == bool(is_retail):
        raise ValidationError('Выберите покупателя из базы или розничный вариант.')
    order = DigitalOrder.objects.create(supplier=supplier, buyer_id=buyer_id, is_retail=bool(is_retail), items=rows,
        cost=sum((money(row['cost']) for row in rows), ZERO), price=total, creation_key=key,
        source='manual', state=DigitalOrder.State.READY, checklist_received=True, goods_received=True,
        comment=comment, source_url=source_url, edited_by=actor)
    from .models import SupplierPurchase
    SupplierPurchase.objects.create(order=order, message=None, amount=order.cost, occurred_at=timezone.now())
    for number in numbers:
        OrderReference.objects.create(supplier=supplier, order=order, number=number)
    if secret:
        from .ingestion import store_manual_goods
        store_manual_goods(order, secret, actor)
    return confirm_order(actor=actor, order_id=order.pk, revision=order.revision)


def _sale_contract(order, sale):
    if (sale.sale_type != Sale.SaleType.DIGITAL or sale.operation_kind != Sale.OperationKind.DIGITAL_PRODUCT
            or sale.warehouse_id or sale.payment_method != Sale.PaymentMethod.BANK_CARD
            or sale.cd_items.exists() or sale.tech_items.exists() or sale.consignment_items.exists()):
        raise ValidationError('Нарушен состав цифровой продажи.')
    rows = list(sale.custom_items.all())
    if (not rows or any(row.quantity != 1 or row.unit_cost_snapshot is None
                or row.system_product_id != Sale.OperationKind.DIGITAL_PRODUCT or row.avito_commission_amount for row in rows)
            or sum((row.line_total for row in rows), ZERO) != sale.total_amount
            or sale.total_amount != order.price
            or sum((row.unit_cost_snapshot for row in rows), ZERO) != order.cost):
        raise ValidationError('Снимки цифровой продажи не совпадают с подтверждённым заказом.')


@retry_database_lock
@transaction.atomic
def complete_sale(*, actor, sale_id):
    actor = require(actor, 'digital_sales.complete_digital_sales', 'sales.mark_sale_paid')
    # Единый порядок: поставщик → покупатель → заказ → Sale. IMMEDIATE сериализует SQLite.
    source = DigitalOrder.objects.get(sale_id=sale_id)
    supplier = Supplier.objects.select_for_update().get(pk=source.supplier_id)
    buyer = None if source.is_retail else Buyer.objects.select_for_update().get(pk=source.buyer_id)
    order = DigitalOrder.objects.select_for_update().get(pk=source.pk)
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.is_cancelled:
        raise ValidationError('Отменённую цифровую продажу завершать нельзя.')
    if sale.is_completed:
        return sale
    if order.review_reason:
        raise ValidationError('Перед завершением требуется разрешить расхождения цифрового заказа.')
    _sale_contract(order, sale)
    # Оба баланса могут уйти в минус: долг учитывается тем же журналом, без новой кассовой операции.
    if buyer is not None:
        BalanceMovement.objects.create(buyer=buyer, sale=sale, delta=-sale.total_amount, kind='sale', actor=actor,
                                      reason=f'Оплата {sale.visible_id}')
    if order.cost:
        BalanceMovement.objects.create(supplier=supplier, sale=sale, delta=-order.cost, kind='sale', actor=actor,
                                      reason=f'Себестоимость {sale.visible_id}')
    if buyer is not None:
        buyer.save(update_fields=['updated_at'])
    if order.is_retail:
        sale.cash_received_amount = sale.total_amount
    sale.order_status, sale.payment_status = Sale.OrderStatus.DELIVERED, Sale.PaymentStatus.PAID
    sale.completed_at = sale.paid_at = timezone.now()
    sale.paid_by = actor
    # Розница фиксирует новое поступление по карте; расчёт с балансом сохраняет NULL.
    sale.full_clean()
    sale.save(update_fields=['order_status', 'payment_status', 'completed_at', 'paid_at', 'paid_by', 'cash_received_amount', 'updated_at'])
    order.state, order.revision = DigitalOrder.State.COMPLETED, order.revision + 1
    order.save(update_fields=['state', 'revision', 'updated_at'])
    AuditEvent.objects.create(order=order, actor=actor, kind='sale_completed', detail=f'sale={sale.pk}')
    if buyer is not None:
        from .customer_receipts import enqueue_sale_receipt
        enqueue_sale_receipt(buyer, sale=sale)
    from .notifications import enqueue_order
    enqueue_order(order, event=f'completed:{order.revision}')
    return sale


@retry_database_lock
@transaction.atomic
def cancel_digital_sale(*, actor, sale_id, comment):
    from sales.services import SaleCancellationResult
    actor = require(actor, 'digital_sales.cancel_digital_sales', 'sales.cancel_sale')
    comment = str(comment or '').strip()
    if not comment:
        raise ValidationError('Укажите причину отмены.')
    source = DigitalOrder.objects.get(sale_id=sale_id)
    Supplier.objects.select_for_update().get(pk=source.supplier_id)
    buyer = None if source.is_retail else Buyer.objects.select_for_update().get(pk=source.buyer_id)
    order = DigitalOrder.objects.select_for_update().get(pk=source.pk)
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.is_cancelled:
        return SaleCancellationResult(sale=sale, cancelled=False)
    buyer_was_charged = buyer is not None and BalanceMovement.objects.filter(sale=sale, kind='sale', buyer=buyer).exists()
    for movement in BalanceMovement.objects.filter(sale=sale, kind='sale').select_for_update():
        BalanceMovement.objects.create(buyer_id=movement.buyer_id, supplier_id=movement.supplier_id,
            sale=sale, kind='reversal', delta=-movement.delta, reversal_of=movement,
            actor=actor, reason=comment[:500])
    if buyer is not None:
        buyer.save(update_fields=['updated_at'])
    if source.is_retail and sale.payment_status == Sale.PaymentStatus.PAID:
        sale.refunded_amount = sale.cash_received_amount or ZERO
    sale.cancelled_at, sale.cancelled_by, sale.cancellation_comment = timezone.now(), actor, comment
    sale.full_clean()
    sale.save(update_fields=['cancelled_at', 'cancelled_by', 'cancellation_comment', 'refunded_amount', 'updated_at'])
    order.state, order.revision = DigitalOrder.State.CANCELLED, order.revision + 1
    order.save(update_fields=['state', 'revision', 'updated_at'])
    AuditEvent.objects.create(order=order, actor=actor, kind='sale_cancelled', detail=f'sale={sale.pk}')
    if buyer is not None:
        from .chat_balances import enqueue_balance
        if buyer_was_charged:
            enqueue_balance(buyer, event=f'cancel:{sale.pk}')
    from .notifications import enqueue_order
    enqueue_order(order, event=f'cancelled:{order.revision}')
    from .ingestion import expected_balance
    from .notifications import enqueue_alert
    expected = expected_balance(order.supplier)
    if order.supplier.balance != expected:
        enqueue_alert(f'cancel_balance:{sale.pk}',
            f'Отменена цифровая продажа {sale.visible_id}. Внутреннее списание сторнировано.\n'
            f'Внутренний баланс: {order.supplier.balance} ₽; ожидаемый по закупкам: {expected} ₽.\n'
            'Отмена в CRM не подтверждает возврат денег поставщиком. Требуется сверка.')
    return SaleCancellationResult(sale=sale, cancelled=True)
