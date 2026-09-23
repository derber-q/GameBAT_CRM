"""Ввод ранее переданной реализации без повторного списания физического склада."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from catalog.audit import field_change, record_product_changes
from catalog.models import ProductChangeEvent
from partners.models import SalesPlatform
from warehouse.models import Warehouse
from .services import _configuration, _positive_quantity, _positive_receivable


@transaction.atomic
def add_opening_balances(*, actor, warehouse_id, source_key, rows):
    """Создать партии по подтверждённому источнику и обновить агрегат товара.

    Источник и номер строки образуют устойчивый ключ против повторного импорта.
    Одинаковые товары с разным вознаграждением остаются разными партиями.
    Сервис не является обычной передачей и не создаёт денежную операцию.
    """
    warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    results = []
    for row in rows:
        kind = row['kind']
        model, stock_model, _, _, product_field = _configuration(kind)
        product = model.objects.active().select_for_update().get(pk=row['product_id'])
        platform = SalesPlatform.objects.get(pk=row['platform_id'])
        quantity = _positive_quantity(row['quantity'])
        reward = _positive_receivable(row['reward'])
        lot_key = f'{source_key}:{row["source_row"]}'
        if len(lot_key) > 100:
            raise ValidationError('Слишком длинный ключ источника.')
        lookup = dict(platform=platform, warehouse=warehouse, lot_key=lot_key, **{product_field: product})
        if stock_model.objects.filter(**lookup).exists():
            raise ValidationError('Этот источник уже загружен. Повторная загрузка запрещена.')
        stock = stock_model(**lookup, quantity=quantity, receivable_per_unit=reward)
        stock.full_clean()
        stock.save()
        before = product.quantity_on_consignment
        product.quantity_on_consignment += quantity
        product.save(update_fields=['quantity_on_consignment'])
        record_product_changes(
            actor=actor, instance=product, source=ProductChangeEvent.Source.CRM,
            changes=[
                field_change(field_name=f'consignment_stock_{kind}_{stock.pk}',
                             field_label=f'Ввод ранее переданной реализации: {platform.name}, партия {lot_key}', old_value=0, new_value=quantity),
                field_change(field_name='quantity_on_consignment', field_label='Всего на реализации', old_value=before,
                             new_value=product.quantity_on_consignment),
                field_change(field_name=f'consignment_reward_{kind}_{stock.pk}', field_label='Вознаграждение за единицу',
                             old_value='', new_value=reward),
            ],
        )
        results.append(stock)
    return results
