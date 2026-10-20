"""Допуск поставщиков к новым назначениям; цены и исторические снимки сохраняются."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from partners.models import Supplier

from .audit import field_change, record_product_changes
from .models import ProductChangeEvent, ProductSupplierExclusion


def exclusion_keys(product_keys=None):
    rows = ProductSupplierExclusion.objects.all()
    if product_keys is not None:
        keys = set(product_keys)
        rows = rows.filter(Q(cd_id__in=[pk for kind, pk in keys if kind == 'cd']) |
                           Q(tech_id__in=[pk for kind, pk in keys if kind == 'tech']))
    return {('cd' if cd else 'tech', cd or tech, supplier) for cd, tech, supplier in rows.values_list('cd_id', 'tech_id', 'supplier_id')}


def validate_supplier_assignments(assignments):
    """Одна выборка исключений для всего нового состава, включая источник цены."""
    assignments = list(assignments)
    blocked = exclusion_keys((kind, pk) for kind, pk, _supplier, _label in assignments)
    for kind, pk, supplier_id, label in assignments:
        if (kind, pk, supplier_id) in blocked:
            raise ValidationError(f'{label}: поставщик исключён из подбора этого товара. Выберите допустимого поставщика или сформируйте новый прайс.')


@transaction.atomic
def set_supplier_exclusions(*, product, supplier_ids, actor, creating=False):
    product = type(product).objects.select_for_update().get(pk=product.pk)
    permission = f'catalog.{"add" if creating else "change"}_{product._meta.model_name}'
    if not (actor.is_superuser or actor.has_perm(permission)):
        raise PermissionDenied('Нет права изменять исключения поставщиков этого товара.')
    if product.is_archived:
        raise ValidationError('Удалённый товар нельзя изменять.')
    try:
        selected = {int(value) for value in supplier_ids}
    except (TypeError, ValueError) as exc:
        raise ValidationError('Выберите существующих поставщиков.') from exc
    suppliers = {s.pk: s for s in Supplier.objects.filter(pk__in=selected)}
    if selected != set(suppliers):
        raise ValidationError('Один из поставщиков больше не существует.')
    lookup = {product._meta.model_name: product}
    old = {e.supplier_id: e for e in ProductSupplierExclusion.objects.select_for_update().select_related('supplier').filter(**lookup)}
    changes = []
    for supplier_id in sorted(set(old) - selected):
        supplier = old[supplier_id].supplier
        old[supplier_id].delete()
        changes.append(field_change(field_name=f'supplier_exclusion_{supplier_id}', field_label=f'Не участвует в подборе: {supplier.safe_label}', old_value='Да', new_value='Нет'))
    for supplier_id in sorted(selected - set(old)):
        ProductSupplierExclusion.objects.create(**lookup, supplier=suppliers[supplier_id], created_by=actor)
        changes.append(field_change(field_name=f'supplier_exclusion_{supplier_id}', field_label=f'Не участвует в подборе: {suppliers[supplier_id].safe_label}', old_value='Нет', new_value='Да'))
    record_product_changes(actor=actor, instance=product, changes=changes, source=ProductChangeEvent.Source.NOMENCLATURE)
    return bool(changes)
