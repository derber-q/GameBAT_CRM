"""Только реально доступные предложения с эффективной индивидуальной наценкой."""
from django.core.exceptions import ValidationError
from digital_prices.models import Product, BuyerMarkup
from digital_prices.services import selling_price, effective_rule
from digital_prices.classification import COUNTRIES, region_code
from .public import title

KINDS = {'ps': 'Подписки PlayStation', 'xbox': 'Подписки Xbox', 'game': 'Игры PlayStation',
    'xbox_game': 'Игры Xbox', 'code': 'Цифровые коды', 'empty': 'Новые аккаунты',
    'cprod': 'Цифровые услуги', 'steam_topup': 'Пополнение Steam', 'steam_gift': 'Подарки Steam'}
UNSET = object()


def markup(product, buyer_id):
    value = BuyerMarkup.objects.filter(product=product, buyer_id=buyer_id).values_list('markup', flat=True).first()
    return product.markup if value is None else value


def validate(product, buyer_id, *, fee=UNSET):
    req = product.requirements
    if (product.api_version != 2 or product.external_id.startswith('v1_') or product.mapping_issue or
            product.requires_review or product.currency != 'RUB' or product.availability != 'yes' or
            product.source_type not in KINDS or product.fulfillment not in ('manual', 'automatic') or
            (markup(product, buyer_id) if fee is UNSET else fee) is None or not isinstance(req, dict)):
        raise ValidationError('Товар сейчас недоступен для оформления.')
    if set(req) - {'account', 'account_modes', 'account_format', 'account_hint', 'parameters', 'delivery'}:
        raise ValidationError('Требования товара нуждаются в проверке.')
    if (set(req.get('parameters', [])) - {'amount'} or set(req.get('delivery', [])) - {'login', 'friend_link'} or
            req.get('account_format', '') not in ('', 'text', 'credentials')):
        raise ValidationError('Для товара требуется неподдерживаемый способ оформления.')
    if req.get('account') and (not isinstance(req.get('account_modes'), list) or not req['account_modes']
            or any(mode not in ('existing', 'new') for mode in req['account_modes'])):
        raise ValidationError('Не подтверждён способ передачи аккаунта.')
    if product.purchase_cost is None and product.source_type not in ('steam_topup', 'steam_gift'):
        raise ValidationError('Цена товара временно недоступна.')
    return product


def products(buyer_id, *, kind=None, query=''):
    rows = Product.objects.filter(api_version=2, requires_review=False, mapping_issue='', availability='yes', currency='RUB')
    if kind:
        rows = rows.filter(source_type=kind)
    if query:
        rows = rows.filter(source_name__icontains=query[:150])
    result = []
    # Наличие нулевой наценки отличается от отсутствующей: товар с нулём доступен.
    overrides = dict(BuyerMarkup.objects.filter(buyer_id=buyer_id, product_id__isnull=False).values_list('product_id', 'markup'))
    for product in rows.order_by('section', 'position', 'source_name', 'pk'):
        value = overrides.get(product.pk)
        if (product.markup if value is None else value) is None:
            continue
        try:
            validate(product, buyer_id, fee=product.markup if value is None else value)
        except ValidationError:
            continue
        result.append(product)
    return result


def caption(product, buyer_id, *, mode=''):
    price = selling_price(product.purchase_cost, 'RUB', markup(product, buyer_id), effective_rule(product))
    if mode == 'new' and price is not None:
        from digital_sales.models import Buyer
        from digital_prices.customer_terms import new_account_fee
        price += new_account_fee(Buyer.objects.get(pk=buyer_id).name) or 0
    name = title(product.display_name or product.source_name)
    family = code_family(product) if product.source_type == 'code' else ''
    if family and family.casefold() not in name.casefold():
        name = family + ' · ' + name
    region = COUNTRIES.get(region_code(product.region), title(product.region)) if product.region else ''
    return (name + (' · ' + region if region else '')
            + (' · новый аккаунт' if mode == 'new' else ' · существующий аккаунт' if mode == 'existing' else '')
            + (' · по расчёту' if price is None else f' · {price:.0f} ₽'))


def code_family(product):
    return title(product.attributes.get('family') or product.platform or 'Цифровые коды')


def compatibility(product, mode):
    req = product.requirements
    return (product.platform.casefold(), product.region.casefold(), mode, req.get('account_format', 'credentials'))
