"""Фактические затраты рейса: исходные количества отдельно от сверенного состава."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .models import ProductReferenceMixin


class TripArrival(models.Model):
    trip = models.OneToOneField('SupplierOrderBatch', on_delete=models.PROTECT, related_name='arrival')
    usdt_aed = models.DecimalField('AED за 1 USDT', max_digits=20, decimal_places=6)
    usdt_rub = models.DecimalField('RUB за 1 USDT', max_digits=20, decimal_places=6)
    actual_delivery = models.DecimalField('Фактическая доставка, RUB', max_digits=20, decimal_places=2)
    arrived_at = models.DateTimeField(null=True, blank=True, editable=False)
    arrived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    revision = models.PositiveIntegerField(default=1, editable=False)
    reviewed_orders = models.JSONField(default=list, editable=False)
    purchase_total = models.DecimalField(max_digits=20, decimal_places=2, default=0, editable=False)
    control_total = models.DecimalField(max_digits=20, decimal_places=2, default=0, editable=False)
    finalized_at = models.DateTimeField(null=True, blank=True, editable=False)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    proposed_prices = models.JSONField(default=dict, editable=False)
    applied_prices = models.JSONField(default=dict, editable=False)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(usdt_aed__gt=0, usdt_rub__gt=0, actual_delivery__gte=0), name='trip_arrival_positive_parameters'),
        ]

    @property
    def arrived(self):
        return self.arrived_at is not None

    @property
    def finalized(self):
        return self.finalized_at is not None

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.get(pk=self.pk)
            fields = ('trip_id', 'usdt_aed', 'usdt_rub', 'actual_delivery')
            if stored.arrived and any(getattr(stored, name) != getattr(self, name) for name in fields):
                raise ValidationError('Курсы и фактическая доставка прибывшего рейса зафиксированы.')
            if stored.finalized and any(getattr(stored, name) != getattr(self, name) for name in
                    ('control_total', 'purchase_total', 'finalized_at', 'finalized_by_id', 'proposed_prices', 'arrived_at')):
                raise ValidationError('Итоговая финализация рейса уже зафиксирована.')
            if stored.arrived and not self.arrived and self.trip.trip_orders.filter(operations__calculation__arrival_id=self.pk).exists():
                raise ValidationError('После создания первой операции нельзя снять прибытие рейса.')
        return super().save(*args, **kwargs)


class TripCostRow(ProductReferenceMixin):
    arrival = models.ForeignKey(TripArrival, on_delete=models.PROTECT, related_name='rows')
    order = models.ForeignKey('CustomerProcurementOrder', on_delete=models.PROTECT, related_name='arrival_rows')
    order_item = models.ForeignKey('CustomerProcurementOrderItem', on_delete=models.PROTECT, related_name='arrival_rows')
    allocation = models.ForeignKey('SupplierTripAllocation', on_delete=models.PROTECT, related_name='arrival_rows')
    supplier = models.ForeignKey('partners.Supplier', on_delete=models.PROTECT, related_name='+')
    portion = models.CharField(max_length=16)
    original_quantity = models.PositiveIntegerField()
    actual_quantity = models.PositiveIntegerField()
    price_aed = models.DecimalField(max_digits=20, decimal_places=6)
    weight_grams_snapshot = models.PositiveIntegerField()
    preliminary_delivery = models.DecimalField(max_digits=20, decimal_places=2)
    tariff_snapshot = models.JSONField(default=dict)
    purchase_unit_cost = models.DecimalField(max_digits=20, decimal_places=2)
    delivery_total = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    final_total = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    customer_price = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    unit_discount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    line_note = models.TextField(blank=True)

    class Meta:
        default_permissions = ()
        ordering = ('order_id', 'supplier_id', 'pk')
        constraints = [
            models.UniqueConstraint(fields=('arrival', 'allocation', 'portion'), name='unique_arrival_allocation_portion'),
            models.CheckConstraint(condition=models.Q(original_quantity__gt=0, actual_quantity__lte=models.F('original_quantity')), name='trip_actual_not_above_ordered'),
            models.CheckConstraint(condition=models.Q(delivery_total__gte=0, final_total__gte=0, purchase_unit_cost__gte=0, preliminary_delivery__gte=0), name='trip_cost_amounts_nonnegative'),
        ]

    @property
    def missing_quantity(self):
        return self.original_quantity - self.actual_quantity

    @property
    def purchase_total(self):
        return self.purchase_unit_cost * self.actual_quantity

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.select_related('arrival').get(pk=self.pk)
            frozen = ('arrival_id', 'order_id', 'order_item_id', 'allocation_id', 'supplier_id', 'portion',
                      'product_kind', 'cd_id', 'tech_id', 'original_quantity', 'price_aed', 'weight_grams_snapshot',
                      'preliminary_delivery', 'tariff_snapshot', 'purchase_unit_cost', 'customer_price')
            if any(getattr(stored, name) != getattr(self, name) for name in frozen):
                raise ValidationError('Исходная закупочная позиция рейса зафиксирована.')
            if stored.arrival.finalized and any(getattr(stored, name) != getattr(self, name) for name in
                    ('actual_quantity', 'delivery_total', 'final_total')):
                raise ValidationError('Состав и затраты финализированного рейса менять нельзя.')
        return super().save(*args, **kwargs)
