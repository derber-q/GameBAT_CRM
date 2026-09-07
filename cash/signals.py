from django.db.models.signals import post_save
from django.dispatch import receiver

from warehouse.models import Warehouse

from .models import CashRegister


@receiver(post_save, sender=Warehouse, dispatch_uid="cash.ensure_register_for_warehouse")
def ensure_cash_register(sender, instance, raw=False, **kwargs):
    """Создаёт нулевую кассу вместе со складом и восстанавливает пропущенную связь."""
    if not raw:
        CashRegister.objects.get_or_create(warehouse=instance)
