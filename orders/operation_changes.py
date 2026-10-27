"""Проверка редактируемого состава и подписанное подтверждение отличий от заказа."""
import hashlib
import json
from decimal import Decimal

from django import forms
from django.core import signing
from django.core.exceptions import ValidationError

from catalog.models import CD, Tech

SALT = 'resource.trip-operation-changes.v1'


class ChangesConfirmationRequired(ValidationError):
    def __init__(self, *, actor, draft, rows, changes, details):
        self.rows = rows
        self.changes = changes
        self.token = signing.dumps(confirmation_values(actor, draft, rows, details), salt=SALT, compress=True)
        super().__init__('Проверьте список изменений и подтвердите создание документа.')


def confirmation_values(actor, draft, rows, details):
    encoded = json.dumps({'rows': rows, 'details': details}, sort_keys=True, ensure_ascii=False, default=str)
    return {'actor': actor.pk, 'draft': draft['key'], 'fingerprint': hashlib.sha256(encoded.encode()).hexdigest()}


def confirm_changes(*, actor, draft, rows, changes, details, token=''):
    if not changes:
        return
    try:
        accepted = signing.loads(token, salt=SALT, max_age=1800)
    except (signing.BadSignature, TypeError):
        accepted = None
    if accepted != confirmation_values(actor, draft, rows, details):
        raise ChangesConfirmationRequired(actor=actor, draft=draft, rows=rows, changes=changes, details=details)


def draft_rows(draft):
    return [{**row, 'trip_row': str(index + 1)} for index, row in enumerate(draft['calculation']['rows'])]


def _amount(value, *, precision=2, label='Сумма'):
    try:
        return forms.DecimalField(max_digits=20, decimal_places=precision, min_value=0).clean(value)
    except ValidationError as exc:
        raise ValidationError(f'{label}: укажите неотрицательное число с точностью до {precision} знаков.') from exc


def resolve_rows(*, draft, lines, supply=False):
    """Исходные партии сохраняют снимки; добавленные продажи получают цену/стоимость из каталога."""
    originals = {row['trip_row']: row for row in draft_rows(draft)}
    products = {}
    for kind, model in (('cd', CD), ('tech', Tech)):
        ids = {str(row.get('product_id')) for row in lines if row.get('product_type') == kind}
        if any(not value.isdecimal() for value in ids):
            raise ValidationError('Выберите существующий товар из базы.')
        products.update({(kind, product.pk): product for product in model.objects.active().select_for_update().filter(pk__in=ids)})
    result, changes, used = [], [], set()
    explicit_references = any('trip_row' in row for row in lines)
    for index, raw in enumerate(lines):
        kind = raw.get('product_type')
        try:
            product = products[kind, int(raw.get('product_id'))]
            qty = forms.IntegerField(min_value=0, max_value=2147483647).clean(raw.get('quantity'))
        except (KeyError, ValueError, TypeError, ValidationError) as exc:
            raise ValidationError('Выберите товар из базы и укажите целое неотрицательное количество.') from exc
        reference = str(raw.get('trip_row') or '')
        if not explicit_references:
            # Совместимость внутренних вызовов: сохраняем порядок отдельных партий источника.
            candidate = originals.get(str(index + 1))
            if candidate and (candidate['product_type'], candidate['product_id']) == (kind, product.pk):
                reference = str(index + 1)
        original = originals.get(reference) if reference else None
        if reference and (original is None or reference in used or
                (original['product_type'], original['product_id']) != (kind, product.pk)):
            raise ValidationError('Исходная строка заказа изменена или указана повторно. Обновите форму.')
        if original:
            used.add(reference)
        if not qty:
            if original:
                changes.append(f'Удалён товар «{product.name}»: {original["quantity"]} → 0 шт.')
            continue
        row = dict(original) if original else {
            'product_type': kind, 'product_id': product.pk, 'label': product.name,
            'trip_row': '', 'origin': 'catalog', 'unit_cost': str(product.cost),
            'unit_price': str(product.wholesale_price) if product.wholesale_price is not None else '',
        }
        row['quantity'] = qty
        if original and qty != original['quantity']:
            changes.append(f'«{product.name}»: количество {original["quantity"]} → {qty} шт.')
        if not original:
            changes.append(f'Добавлен товар «{product.name}»: {qty} шт.')
        if supply:
            try:
                supplier_id = forms.IntegerField(min_value=1).clean(raw.get('supplier_id'))
            except ValidationError as exc:
                raise ValidationError(f'{product.name}: выберите поставщика.') from exc
            cost = _amount(raw.get('purchase_unit_cost'), precision=6, label=f'{product.name}: себестоимость')
            if original and Decimal(original['unit_cost']) != cost:
                changes.append(f'«{product.name}»: себестоимость {original["unit_cost"]} → {cost} ₽/шт.')
            if original and original['supplier_id'] != supplier_id:
                from partners.models import Supplier
                letters = dict(Supplier.objects.filter(pk__in=[original['supplier_id'],supplier_id]).values_list('pk','letter'))
                changes.append(f'«{product.name}»: поставщик [{letters.get(original["supplier_id"], "?")}] → [{letters.get(supplier_id, "?")}].')
            row.update(supplier_id=supplier_id, unit_cost=str(cost), purchase_unit_cost=str(cost))
        else:
            if row['unit_price'] in ('', 'None'):
                raise ValidationError(f'{product.name}: в карточке не задана оптовая цена.')
            discount = forms.DecimalField(max_digits=20, decimal_places=2).clean(raw.get('unit_discount') or '0')
            if discount > Decimal(row['unit_price']):
                raise ValidationError(f'{product.name}: скидка превышает цену товара.')
            row.update(unit_discount=str(discount), line_note=str(raw.get('line_note') or '').strip())
            if discount:
                changes.append(f'«{product.name}»: {"скидка" if discount > 0 else "доплата"} {abs(discount):.2f} ₽/шт.; цена {Decimal(row["unit_price"]) - discount:.2f} ₽/шт.')
        if not original:
            changes.append(f'«{product.name}»: себестоимость {row["unit_cost"]} ₽/шт.' +
                           ('' if supply else f', цена покупателя {row["unit_price"]} ₽/шт.'))
        result.append(row)
    for reference, original in originals.items():
        if reference not in used:
            changes.append(f'Удалён товар «{original["label"]}»: {original["quantity"]} → 0 шт.')
    if not result:
        raise ValidationError('В документе должен остаться хотя бы один товар с положительным количеством.')
    if supply:
        from partners.models import Supplier
        ids = {row['supplier_id'] for row in result}
        if Supplier.objects.filter(pk__in=ids).count() != len(ids):
            raise ValidationError('Выберите существующих поставщиков.')
    return result, changes


def operation_snapshot(draft, rows, changes):
    return {**draft['calculation'], 'source_rows': draft['calculation']['rows'],
            'rows': rows, 'confirmed_changes': changes}
