"""Приём физически полученного возврата; идемпотентность задаёт документ-источник."""
from django.db import transaction
from catalog.audit import record_product_changes, stock_change
from catalog.models import ProductChangeEvent
from .models import Warehouse
from .services import normalise_product_lines, stock_configuration


@transaction.atomic
def receive_return(*, actor, warehouse_id, lines, label, sale_id):
    warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    for line in normalise_product_lines(lines):
        product_model, stock_model, field = stock_configuration(line["product_type"])
        product = product_model.objects.select_for_update().get(pk=line["product_id"])
        stock, _ = stock_model.objects.get_or_create(warehouse=warehouse, **{field: product})
        old_quantity = stock.quantity
        stock.quantity += line["quantity"]
        stock.full_clean()
        stock.save(update_fields=["quantity"])
        record_product_changes(actor=actor, instance=product, source=ProductChangeEvent.Source.CRM,
                               action_kind=ProductChangeEvent.ActionKind.SALE, action_object_id=sale_id,
                               action_label=label, changes=[stock_change(warehouse=warehouse, old_quantity=old_quantity, new_quantity=stock.quantity)])
