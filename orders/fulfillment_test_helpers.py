"""Реконструкция старых документов для регрессии исторической себестоимости; новый UI использует общие затраты рейса."""
from uuid import uuid4
from django.db import transaction
from core.db_retry import retry_database_lock
from .models import CustomerProcurementOrder
from .fulfillment import calculation, _create_legacy_order_supply as create_order_supply
from .services import receive_stock_order


@retry_database_lock
@transaction.atomic
def receive_with_test_rates(*, actor, order_id, warehouse_id):
    order=CustomerProcurementOrder.objects.select_for_update().select_related('price_list').get(pk=order_id)
    if not order.trip_id:
        return receive_stock_order(actor=actor,order_id=order_id,warehouse_id=warehouse_id)
    if order.supply_id:
        return order
    snapshot=calculation(order,usd_rub=order.price_list.exchange_rate_usdt_rub,aed_rub=order.price_list.exchange_rate_aed_rub)
    create_order_supply(actor=actor,warehouse_id=warehouse_id,
        draft={'key':str(uuid4()),'order_id':order.pk,'calculation':snapshot})
    return CustomerProcurementOrder.objects.select_related('supply').get(pk=order_id)
