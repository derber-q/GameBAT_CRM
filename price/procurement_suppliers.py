"""Выбор поставщика из сохранённых предложений конкретной версии прайса."""
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator

from catalog.supplier_exclusions import exclusion_keys


def pricing_snapshot(item):
    """Отпечаток всех расчётных полей и корректировок, включая невыбранных поставщиков.

    Это проверка актуальности формы, а не замена проверок прав и входных данных.
    Вызывающий код массово загружает обе связи, чтобы не создавать N+1.
    """
    data = {f.attname: str(getattr(item, f.attname)) for f in item._meta.concrete_fields}
    data['overrides'] = sorted((o.supplier_id, str(o.price_aed), o.active, o.updated_at.isoformat())
        for o in item.supplier_price_overrides.all())
    data['offers'] = sorted((o.supplier_id, str(o.price_aed)) for o in item.supplier_offers.all())
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def manual_price(value):
    text = str(value).strip().replace(',', '.')
    if len(text) > 32 or not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,6})?', text):
        raise ValidationError('Моя цена AED: укажите положительное число, не более 6 знаков после запятой.')
    result = Decimal(text)
    DecimalValidator(max_digits=20, decimal_places=6)(result)
    if result <= 0:
        raise ValidationError('Моя цена AED должна быть больше нуля.')
    return result


def can_change_supplier(user):
    return user.is_superuser or (
        user.has_perm('price.view_supplier_prices') and user.has_perm('price.change_procurement_markup')
    )


def supplier_base_price(item, price_list, price_aed):
    # Как при создании версии: промежуточная сумма USDT не округляется.
    if price_list.exchange_rate_usdt_aed and price_list.exchange_rate_usdt_rub:
        amount = price_aed / price_list.exchange_rate_usdt_aed * price_list.exchange_rate_usdt_rub
    else:
        amount = price_aed * item.exchange_rate_aed_rub
    amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    DecimalValidator(max_digits=20, decimal_places=2)(amount)
    if not amount.is_finite() or amount < 0:
        raise ValidationError('Не удалось рассчитать базовую цену выбранного поставщика.')
    return amount


def prepare_supplier_choices(items, price_list):
    items = list(items)
    excluded = exclusion_keys((item.product_kind, item.product_id) for item in items)
    for item in items:
        offers = {offer.supplier_id: offer for offer in item.supplier_offers.all()}
        overrides = {o.supplier_id:o for o in item.supplier_price_overrides.all()}
        # Старые версии могли сохранить только победителя; текущие цены поставщиков
        # не являются доказательством их предложений на дату такого прайса.
        offers.setdefault(item.selected_supplier_id, SimpleNamespace(
            supplier_id=item.selected_supplier_id, supplier=item.selected_supplier, price_aed=item.supplier_price_aed,
        ))
        item.pricing_initial = pricing_snapshot(item)
        item.supplier_choices = []
        for offer in sorted(offers.values(), key=lambda offer: (offer.supplier.letter.casefold(), offer.supplier_id)):
            selected = offer.supplier_id == item.selected_supplier_id
            override = overrides.get(offer.supplier_id)
            manual = bool(override and override.active)
            effective_price = override.price_aed if manual else offer.price_aed
            label = lambda value: format(value, '.6f').rstrip('0').rstrip('.')
            item.supplier_choices.append({
                'supplier': offer.supplier,
                'price_aed': effective_price, 'original_price_aed': offer.price_aed,
                'original_price_label': label(offer.price_aed),
                'manual': manual, 'price_label': label(effective_price),
                'can_override': not isinstance(offer, SimpleNamespace),
                'base_price_rub': item.base_price_rub if selected else supplier_base_price(item, price_list, effective_price),
                'selected': selected,
                'is_expensive': (item.product_kind == 'cd' and not selected
                    and effective_price - item.supplier_price_aed >= Decimal('5')),
                'excluded': (item.product_kind, item.product_id, offer.supplier_id) in excluded,
            })
    return items


def _supplier_id(value):
    text = str(value)
    if len(text) > 20 or not text.isascii() or not text.isdecimal() or int(text) <= 0:
        raise ValidationError('Выберите поставщика из предложений этой версии прайса.')
    return int(text)


def apply_supplier_choice(item, price_list, values, actor, excluded):
    baseline = values.get('pricing_initial')
    if baseline is not None and baseline != pricing_snapshot(item):
        raise ValidationError('Расчёт прайса уже изменён. Обновите страницу перед сохранением.')
    manual_values = values.get('manual_prices')
    if manual_values is not None and baseline is None:
        raise ValidationError('Нет исходного снимка расчёта. Обновите страницу перед сохранением.')
    if manual_values == {}:
        manual_values = None
    if 'supplier_id' not in values:
        if manual_values is not None:
            raise ValidationError('Укажите выбранного поставщика для ручной цены.')
        return None
    if 'supplier_initial_id' in values and _supplier_id(values['supplier_initial_id']) != item.selected_supplier_id:
        raise ValidationError('Поставщик в прайсе уже изменён. Обновите страницу перед сохранением.')
    supplier_id = _supplier_id(values['supplier_id'])
    if supplier_id == item.selected_supplier_id and manual_values is None:
        return None
    if not can_change_supplier(actor):
        raise ValidationError('Для смены поставщика и ручной цены нужны права просмотра цен поставщиков и изменения наценки.')
    if item.product.is_archived:
        raise ValidationError('Нельзя назначить нового поставщика удалённому товару.')
    offers = {o.supplier_id:o for o in item.supplier_offers.all()}
    overrides = {o.supplier_id:o for o in item.supplier_price_overrides.all()}
    offer = offers.get(supplier_id)
    if offer is None:
        raise ValidationError('Выбранный поставщик не предлагал этот товар в данной версии прайса.')
    if supplier_id != item.selected_supplier_id and (item.product_kind, item.product_id, supplier_id) in excluded:
        raise ValidationError('Этот поставщик исключён из подбора товара. Выберите другого поставщика.')
    before = (item.selected_supplier_id, item.supplier_price_aed, item.base_price_rub)
    if manual_values is not None:
        if not isinstance(manual_values, dict) or len(manual_values) > len(offers):
            raise ValidationError('Некорректный список ручных цен поставщиков.')
        from .models import ProcurementSupplierPriceOverride
        from catalog.audit import field_change, record_product_changes
        from catalog.models import ProductChangeEvent
        for key, data in manual_values.items():
            key = _supplier_id(key)
            if key not in offers or not isinstance(data, dict) or type(data.get('enabled')) is not bool:
                raise ValidationError('Ручная цена должна относиться к сохранённому предложению этой версии.')
            previous = overrides.get(key)
            active = data['enabled']
            amount = manual_price(data.get('price_aed')) if active else (previous.price_aed if previous else None)
            if not active and previous is None:
                continue
            if previous and previous.active == active and previous.price_aed == amount:
                continue
            if active and (item.product_kind, item.product_id, key) in excluded:
                raise ValidationError('Этот поставщик исключён из подбора товара.')
            old = f'{previous.price_aed} / {previous.active}' if previous else ''
            override = previous or ProcurementSupplierPriceOverride(price_list_item=item, supplier_id=key)
            override.price_aed, override.active, override.updated_by = amount, active, actor
            override.full_clean(); override.save(); overrides[key] = override
            record_product_changes(actor=actor, instance=item.product, source=ProductChangeEvent.Source.CRM,
                changes=[field_change(field_name=f'procurement_manual_{price_list.pk}_{key}',
                    field_label=f'Ручная цена AED прайса №{price_list.pk}, поставщик {key}',
                    old_value=old, new_value=f'{amount} / {active}')])
    override = overrides.get(supplier_id)
    amount = override.price_aed if override and override.active else offer.price_aed
    if amount != item.supplier_price_aed and (item.product_kind, item.product_id, supplier_id) in excluded:
        raise ValidationError('Этот поставщик исключён из подбора товара.')
    same_price = supplier_id == item.selected_supplier_id and amount == item.supplier_price_aed
    item.selected_supplier = offer.supplier
    item.supplier_price_aed = amount
    # Сохранение прочих полей не исправляет прежний снимок базы задним числом.
    if not same_price:
        item.base_price_rub = supplier_base_price(item, price_list, amount)
    return before if before != (supplier_id, amount, item.base_price_rub) else None
