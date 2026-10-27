"""Состояние заказа следует за штатной продажей/приходом, включая административное сохранение."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from sales.models import Sale
from supplies.models import Supply
from .models import TripOrderOperation


@receiver(post_save, sender=Sale)
@receiver(post_save, sender=Supply)
def document_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from .fulfillment import synchronize
    lookup = {'sale_id' if sender is Sale else 'supply_id': instance.pk}
    operation = TripOrderOperation.objects.filter(active=True, **lookup).first()
    if operation:
        if sender is Sale:
            operation.sale = instance
        else:
            operation.supply = instance
        synchronize(operation, actor=getattr(instance, '_trip_actor', None))
