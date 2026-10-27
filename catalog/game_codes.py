"""Коды дисков PlayStation: нормализация, обязательность при приёмке и аудит."""
import re
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import CD, ProductChangeEvent
from .audit import field_change, record_product_changes


def requires_game_codes(product):
    if not isinstance(product, CD):
        return False
    platform = re.sub(r'[^a-z0-9]', '', product.platform.name.casefold())
    return platform in ('ps4', 'ps5', 'playstation4', 'playstation5', 'sonyplaystation4', 'sonyplaystation5')


def normalize_game_codes(value):
    parts = re.split(r'[,;\n]+', str(value or ''))
    codes = []
    for part in parts:
        if not part.strip():
            continue
        code = part.strip()
        match = re.fullmatch(r'(CUSA|PPSA)\s*-?\s*(\d{5,6})', code, re.I)
        if match:
            code = match[1].upper() + '-' + match[2]
        if code not in codes:
            codes.append(code)
    result = ', '.join(codes)
    if not result:
        raise ValidationError('Заполните CUSA/PPSA-код диска.')
    if len(result) > CD._meta.get_field('cusa_ppsa_code').max_length:
        raise ValidationError('Список CUSA/PPSA превышает допустимую длину карточки.')
    return result


def display_game_codes(product):
    value = getattr(product, 'cusa_ppsa_code', '') or ''
    return ', '.join(dict.fromkeys(part.strip() for part in re.split(r'[,;\n]+', value) if part.strip()))


def validate_supply_game_codes(products):
    missing = [product.name for product in products if requires_game_codes(product) and not product.cusa_ppsa_code.strip()]
    if missing:
        raise ValidationError('Для дисков PS4/PS5 заполните CUSA/PPSA в номенклатуре: ' + '; '.join(missing))


@transaction.atomic
def set_game_codes(*, actor, product_id, value):
    if not actor.has_perm('catalog.change_cd_cusa_ppsa_code'):
        raise PermissionDenied('Нет права изменения CUSA/PPSA.')
    try:
        product = CD.objects.active().select_for_update().get(pk=product_id)
    except (CD.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError('Диск не найден.') from exc
    result = normalize_game_codes(value)
    before = product.cusa_ppsa_code
    if before != result:
        product.cusa_ppsa_code = result
        product.full_clean(exclude=[field.name for field in product._meta.fields if field.name != 'cusa_ppsa_code'])
        product.save(update_fields=['cusa_ppsa_code'])
        record_product_changes(actor=actor, instance=product, source=ProductChangeEvent.Source.CRM,
            changes=[field_change(field_name='cusa_ppsa_code', field_label='CUSA/PPSA', old_value=before, new_value=result)])
    return product
