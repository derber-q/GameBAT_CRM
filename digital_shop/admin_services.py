"""Административные действия с явным аудитом; новые покупки здесь не создаются."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from digital_prices.models import Product, CatalogState
from digital_prices.services import require as price_require, CATEGORIES
from digital_sales.services import require
from .models import ShopConfig, ShopChat, PurchaseIntent, AuditEvent
from .services import write_lock


@transaction.atomic
def close_unsubmitted_cart(*, actor, cart_id, reason):
    """Закрывает только черновик, который уже оформлен менеджером; закупки не трогает."""
    from .models import Cart
    actor=require(actor,'digital_shop.manage_shop')
    if not isinstance(reason,str) or not reason.strip():
        raise ValidationError('Укажите причину закрытия черновика.')
    write_lock()
    cart=Cart.objects.select_for_update().get(pk=cart_id)
    if PurchaseIntent.objects.filter(cart=cart).exists():
        raise ValidationError('У корзины уже есть намерение закупки. Нужна отдельная сверка, закрытие черновика запрещено.')
    if cart.state=='closed':
        return cart
    cart.state='closed'
    cart.revision+=1
    cart.encrypted_credentials=''
    cart.quote_id=''
    cart.quote_expires_at=None
    cart.prompt_message_id=None
    cart.save(update_fields=['state','revision','encrypted_credentials','quote_id','quote_expires_at','prompt_message_id','updated_at'])
    AuditEvent.objects.create(actor=actor,kind='cart_closed_without_purchase',detail={'cart':str(cart.pk),'reason':reason[:300]})
    return cart


@transaction.atomic
def map_legacy(*, actor, old_id, new_id):
    from digital_prices.models import BuyerMarkup, AuditEvent as PriceAudit
    price_require(actor, 'edit_markup')
    price_require(actor, 'sync_catalog')
    require(actor, 'digital_shop.manage_shop')
    old = Product.objects.select_for_update().get(pk=old_id, external_id__startswith='v1_code_', superseded_by__isnull=True)
    new = Product.objects.select_for_update().get(pk=new_id, api_version=2)
    if old.source_type != new.source_type or old.currency != new.currency:
        raise ValidationError('Тип или валюта карточек различаются.')
    if new.markup is not None and old.markup is not None and new.markup != old.markup:
        raise ValidationError('У карточек разные общие наценки. Сначала разрешите конфликт.')
    rows = list(BuyerMarkup.objects.select_for_update().filter(product=old))
    for row in rows:
        target = BuyerMarkup.objects.filter(product=new, buyer=row.buyer).first()
        if target and target.markup is not None and row.markup is not None and target.markup != row.markup:
            raise ValidationError('Индивидуальные наценки расходятся. Сначала разрешите конфликт.')
        if target is None:
            BuyerMarkup.objects.create(product=new, buyer=row.buyer, markup=row.markup, edited_by=actor)
        elif target.markup is None and row.markup is not None:
            target.markup, target.edited_by, target.revision = row.markup, actor, target.revision + 1
            target.save()
    if new.markup is None:
        new.markup = old.markup
    new.legacy_external_id, new.mapping_issue = old.external_id, ''
    new.revision += 1
    # Доступность определяется реальными полями последнего API-ответа, а не самим фактом связывания.
    new.requires_review = new.currency != 'RUB' or new.purchase_cost is None or new.availability == 'unknown'
    new.save()
    old.superseded_by, old.requires_review, old.mapping_issue = new, True, 'superseded'
    old.save(update_fields=['superseded_by', 'requires_review', 'mapping_issue'])
    state = CatalogState.objects.select_for_update().get(pk=1)
    state.revision += 1
    state.save(update_fields=['revision'])
    PriceAudit.objects.create(actor=actor, product=new, kind='v2_manual_mapping', detail={'old': old.pk, 'new': new.pk})


@transaction.atomic
def confirm_refund(*, actor, line_id, reason):
    """Только явное подтверждение сотрудника после фактической сверки возврата."""
    import uuid
    from digital_sales.models import BalanceMovement
    from .models import PurchaseLine, BalanceHold, ConfirmedRefund
    actor = require(actor, 'digital_shop.manage_shop', 'digital_sales.adjust_digital_balances')
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 500:
        raise ValidationError('Укажите проверяемое основание подтверждённого возврата (10–500 символов).')
    write_lock()
    line = PurchaseLine.objects.select_for_update().select_related('intent').get(pk=line_id)
    previous = ConfirmedRefund.objects.filter(line=line).first()
    if previous:
        return previous
    if line.status != 'cancelled' or line.settled_at or line.confirmed_cost is None:
        raise ValidationError('Требуется отменённая внешняя позиция без выполненной клиентской продажи.')
    movement = None
    if line.confirmed_cost:
        if not line.supplier_movement_id:
            raise ValidationError('Исходное списание не найдено.')
        movement = BalanceMovement.objects.create(supplier_id=line.supplier_movement.supplier_id, delta=line.confirmed_cost,
            kind='reversal', reversal_of=line.supplier_movement, actor=actor, reason=reason.strip(),
            operation_key=uuid.uuid5(line.intent_id, 'refund:' + line.line_id))
    refund = ConfirmedRefund.objects.create(line=line, amount=line.confirmed_cost, movement=movement, actor=actor, reason=reason.strip())
    hold = BalanceHold.objects.select_for_update().get(intent=line.intent)
    if hold.state != 'active' or hold.remaining < line.client_price:
        raise ValidationError('Резерв требует сверки.')
    hold.remaining -= line.client_price
    if not hold.remaining:
        hold.state = 'settled'
    hold.save(update_fields=['remaining', 'state'])
    line.status, line.settled_at = 'refunded', timezone.now()
    line.save(update_fields=['status', 'settled_at'])
    if not line.intent.lines.filter(settled_at__isnull=True).exists():
        line.intent.state, line.intent.finished_at, line.intent.encrypted_body = 'done', timezone.now(), ''
        line.intent.save(update_fields=['state', 'finished_at', 'encrypted_body'])
    AuditEvent.objects.create(actor=actor, intent=line.intent, kind='refund_confirmed', detail={'line': line.pk})
    return refund


@transaction.atomic
def configure(*, actor, revision, enabled, purchases_enabled, supplier):
    actor = require(actor, 'digital_shop.manage_shop', 'digital_prices.configure_integration')
    row, _ = ShopConfig.objects.get_or_create(pk=1)
    write_lock()
    row.refresh_from_db()
    if row.revision != int(revision):
        raise ValidationError('Настройки уже изменились. Обновите страницу.')
    if enabled or purchases_enabled:
        require(actor, 'digital_sales.create_digital_sales', 'sales.create_sale',
            'digital_sales.complete_digital_sales', 'sales.mark_sale_paid')
        if supplier is None:
            raise ValidationError('Выберите поставщика для учёта.')
    if purchases_enabled and not enabled:
        raise ValidationError('Нельзя включить закупки при выключенном магазине.')
    if row.supplier_id != getattr(supplier, 'pk', None) and PurchaseIntent.objects.exclude(state__in=['done', 'failed']).exists():
        raise ValidationError('Сначала завершите сверку активных закупок прежнего поставщика.')
    row.enabled, row.purchases_enabled, row.supplier = enabled, purchases_enabled, supplier
    row.actor = actor
    row.revision += 1
    row.save()
    AuditEvent.objects.create(actor=actor, kind='configuration', detail={'enabled': enabled,
        'purchases_enabled': purchases_enabled, 'supplier': row.supplier_id})
    return row


@transaction.atomic
def set_chat(*, actor, binding_id, enabled):
    from digital_sales.models import BuyerBalanceChat, Supplier
    require(actor, 'digital_shop.manage_shop')
    row = BuyerBalanceChat.objects.select_for_update().get(pk=binding_id)
    if enabled and (row.buyer_id is None or any(row.pk in s.chat_ids for s in Supplier.objects.all())):
        raise ValidationError('Нужна отдельная группа привязанного покупателя.')
    chat, _ = ShopChat.objects.get_or_create(binding=row)
    chat.enabled = enabled
    chat.save(update_fields=['enabled'])
    AuditEvent.objects.create(actor=actor, kind='chat_switch', detail={'chat': row.pk, 'enabled': enabled})


@transaction.atomic
def discover(*, actor, offer):
    price_require(actor, 'sync_catalog')
    price_require(actor, 'edit_markup')
    require(actor, 'digital_shop.manage_shop')
    # Сетевой ответ уже проверен parse_page; наценка новой карточки всегда отсутствует.
    state = CatalogState.objects.select_for_update().get(pk=1)
    product, created = Product.objects.select_for_update().get_or_create(external_id=offer.identity,
        defaults={'source_name': offer.name, 'source_type': offer.kind, 'currency': offer.currency,
            'last_seen_at': timezone.now(), 'confirmed_at': timezone.now()})
    product.source_name, product.source_type = offer.name, offer.kind
    product.platform, product.region, product.attributes = offer.platform, offer.region, offer.attributes
    product.api_version, product.fulfillment = 2, offer.attributes.get('fulfillment', '')
    product.requirements, product.quantity_limits = offer.attributes.get('requirements', {}), offer.attributes.get('limits', {})
    if offer.cost is not None:
        product.purchase_cost = offer.cost
    product.currency = offer.currency
    product.availability = 'yes' if offer.available is True else 'no' if offer.available is False else 'unknown'
    product.requires_review = offer.available is None or offer.cost is None or offer.currency != 'RUB'
    if not product.category_manual:
        product.category = CATEGORIES.get(offer.kind, 'Другие цифровые предложения')
    product.last_seen_at = product.confirmed_at = timezone.now()
    product.revision += 1
    product.save()
    state.revision += 1
    state.save(update_fields=['revision'])
    AuditEvent.objects.create(actor=actor, kind='product_discovered', detail={'product': product.pk, 'created': created})
    return product


@transaction.atomic
def rescan(*, actor, intent_id):
    require(actor, 'digital_shop.manage_shop')
    write_lock()
    row = PurchaseIntent.objects.select_for_update().get(pk=intent_id)
    if row.state not in ('review', 'uncertain', 'processing'):
        raise ValidationError('Этот заказ сейчас не требует повторной сверки.')
    if row.lease_until and row.lease_until > timezone.now():
        raise ValidationError('Заказ уже проверяется обработчиком.')
    row.state = 'processing' if row.external_order_id else 'uncertain'
    row.next_at, row.owner, row.lease_until = timezone.now(), None, None
    row.save(update_fields=['state', 'next_at', 'owner', 'lease_until'])
    AuditEvent.objects.create(actor=actor, intent=row, kind='manual_rescan')


@transaction.atomic
def approve_result(*, actor, line_id, result):
    require(actor, 'digital_shop.manage_shop', 'digital_sales.view_digital_secrets')
    from .models import PurchaseLine
    from .execution import finalize_line
    write_lock()
    line = PurchaseLine.objects.select_for_update().get(pk=line_id)
    if line.digital_order_id:
        line.digital_order.review_reason = ''
        line.digital_order.save(update_fields=['review_reason'])
    finalize_line(line, result, actor)
    if not line.intent.lines.filter(settled_at__isnull=True).exists():
        line.intent.state, line.intent.finished_at, line.intent.encrypted_body = 'done', timezone.now(), ''
        line.intent.save(update_fields=['state', 'finished_at', 'encrypted_body'])
    AuditEvent.objects.create(actor=actor, intent=line.intent, kind='result_approved', detail={'line': line.pk})


@transaction.atomic
def retry_delivery(*, actor, delivery_id):
    require(actor, 'digital_shop.manage_shop', 'digital_sales.view_digital_secrets')
    from .models import ResultDelivery
    from .public import checked
    from digital_sales.crypto import decrypt
    row = ResultDelivery.objects.select_for_update().get(pk=delivery_id)
    if row.state not in ('uncertain', 'review') or not row.line.encrypted_result:
        raise ValidationError('Повтор выдачи этой записи недоступен.')
    payload = decrypt(row.line.encrypted_result)
    for text in payload.get('parts') or [payload.get('text')]:
        checked(text)
    row.encrypted_text, row.state = row.line.encrypted_result, 'queued'
    row.save(update_fields=['encrypted_text', 'state'])
    AuditEvent.objects.create(actor=actor, intent=row.line.intent, kind='delivery_retry_confirmed', detail={'delivery': row.pk})
