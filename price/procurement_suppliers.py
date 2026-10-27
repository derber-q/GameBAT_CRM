"""Выбор поставщика из сохранённых предложений конкретной версии прайса."""
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator

from catalog.supplier_exclusions import exclusion_keys


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
        # Старые версии могли сохранить только победителя; текущие цены поставщиков
        # не являются доказательством их предложений на дату такого прайса.
        offers[item.selected_supplier_id] = SimpleNamespace(
            supplier_id=item.selected_supplier_id, supplier=item.selected_supplier, price_aed=item.supplier_price_aed,
        )
        item.supplier_choices = []
        for offer in sorted(offers.values(), key=lambda offer: (offer.supplier.letter.casefold(), offer.supplier_id)):
            selected = offer.supplier_id == item.selected_supplier_id
            item.supplier_choices.append({
                'supplier': offer.supplier,
                'price_aed': offer.price_aed,
                'price_label': format(offer.price_aed, '.6f').rstrip('0').rstrip('.'),
                'base_price_rub': item.base_price_rub if selected else supplier_base_price(item, price_list, offer.price_aed),
                'selected': selected,
                'is_expensive': (item.product_kind == 'cd' and not selected
                    and offer.price_aed - item.supplier_price_aed >= Decimal('5')),
                'excluded': (item.product_kind, item.product_id, offer.supplier_id) in excluded,
            })
    return items


def _supplier_id(value):
    text = str(value)
    if len(text) > 20 or not text.isascii() or not text.isdecimal() or int(text) <= 0:
        raise ValidationError('Выберите поставщика из предложений этой версии прайса.')
    return int(text)


def apply_supplier_choice(item, price_list, values, actor, excluded):
    if 'supplier_id' not in values:
        return None
    if 'supplier_initial_id' in values and _supplier_id(values['supplier_initial_id']) != item.selected_supplier_id:
        raise ValidationError('Поставщик в прайсе уже изменён. Обновите страницу перед сохранением.')
    supplier_id = _supplier_id(values['supplier_id'])
    if supplier_id == item.selected_supplier_id:
        return None
    if not can_change_supplier(actor):
        raise ValidationError('Для смены поставщика нужны права просмотра цен поставщиков и изменения наценки.')
    if item.product.is_archived:
        raise ValidationError('Нельзя назначить нового поставщика удалённому товару.')
    offer = next((offer for offer in item.supplier_offers.all() if offer.supplier_id == supplier_id), None)
    if offer is None:
        raise ValidationError('Выбранный поставщик не предлагал этот товар в данной версии прайса.')
    if (item.product_kind, item.product_id, supplier_id) in excluded:
        raise ValidationError('Этот поставщик исключён из подбора товара. Выберите другого поставщика.')
    before = (item.selected_supplier_id, item.supplier_price_aed, item.base_price_rub)
    item.selected_supplier = offer.supplier
    item.supplier_price_aed = offer.price_aed
    item.base_price_rub = supplier_base_price(item, price_list, offer.price_aed)
    return before
