"""Граница редактирования закупки по фактическим последующим операциям."""
from django.core.exceptions import ValidationError


def downstream_lock_reason(order):
    if order.trip_id:
        from .arrival_models import TripArrival
        if TripArrival.objects.filter(trip_id=order.trip_id,arrived_at__isnull=False).exists():
            return 'Рейс приехал: исходные закупочные позиции зафиксированы. Фактические количества сверяются отдельно.'
    if order.trip_id and any(op.active for op in order.operations.all()):
        return f'Заказ №{order.pk} уже передан в продажу или приход. Сначала отмените связанную операцию.'
    if order.supply_id:
        return f'Товары заказа №{order.pk} уже переданы в приход №{order.supply_id}.'
    if order.status == order.Status.COMPLETED:
        return f'Заказ №{order.pk} уже выполнен; его финансовая история зафиксирована.'
    return ''


def require_untransferred_order(order):
    reason = downstream_lock_reason(order)
    if reason:
        raise ValidationError(reason)
