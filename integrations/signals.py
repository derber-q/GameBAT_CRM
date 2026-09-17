from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist

from catalog.models import CD, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock

from .queue import enqueue_profile_sync_after_commit


def _enqueue_for_product(product):
    try:
        profile_id = product.avito_profile.pk
    except (AttributeError, ObjectDoesNotExist):
        return
    enqueue_profile_sync_after_commit(profile_id)


@receiver(post_save, sender=CD, dispatch_uid="avito_sync_cd")
@receiver(post_save, sender=Tech, dispatch_uid="avito_sync_tech")
def product_changed(sender, instance, **kwargs):
    _enqueue_for_product(instance)


@receiver(post_save, sender=CDWarehouseStock, dispatch_uid="avito_sync_cd_stock")
def cd_stock_changed(sender, instance, **kwargs):
    _enqueue_for_product(instance.cd)


@receiver(post_save, sender=TechWarehouseStock, dispatch_uid="avito_sync_tech_stock")
def tech_stock_changed(sender, instance, **kwargs):
    _enqueue_for_product(instance.tech)
