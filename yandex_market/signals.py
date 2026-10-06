from django.db.models.signals import post_save, pre_save
from django.db.models import F
from django.dispatch import receiver

from catalog.models import CD, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock
from .models import OfferConnection
from .queue import product_after_commit


PRODUCT_FIELDS = ("name", "description", "sku", "weight_grams", "yandex_market_price", "is_archived")


@receiver(pre_save, sender=CD, dispatch_uid="ym_cd_before")
@receiver(pre_save, sender=Tech, dispatch_uid="ym_tech_before")
def remember_product(sender, instance, **kwargs):
    instance._ym_previous_fields = sender.objects.filter(pk=instance.pk).values(*PRODUCT_FIELDS).first() if instance.pk else None


@receiver(pre_save, sender=CDWarehouseStock, dispatch_uid="ym_cd_stock_before")
@receiver(pre_save, sender=TechWarehouseStock, dispatch_uid="ym_tech_stock_before")
def remember_quantity(sender, instance, **kwargs):
    instance._ym_previous_quantity = sender.objects.filter(pk=instance.pk).values_list("quantity", flat=True).first() if instance.pk else None


@receiver(post_save, sender=CDWarehouseStock, dispatch_uid="ym_cd_stock_after")
@receiver(post_save, sender=TechWarehouseStock, dispatch_uid="ym_tech_stock_after")
def stock_changed(sender, instance, raw=False, **kwargs):
    if raw or getattr(instance, "_ym_previous_quantity", None) == instance.quantity:
        return
    kind = "cd" if sender is CDWarehouseStock else "tech"
    for pk in OfferConnection.objects.filter(active=True, managed=True, **{f"{kind}_id": getattr(instance, f"{kind}_id")}).values_list("pk", flat=True):
        product_after_commit(pk)


@receiver(post_save, sender=CD, dispatch_uid="ym_cd_after")
@receiver(post_save, sender=Tech, dispatch_uid="ym_tech_after")
def product_changed(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields and not set(update_fields) & {"yandex_market_price", "is_archived", "name", "description", "weight_grams", "sku"}):
        return
    kind = "cd" if sender is CD else "tech"
    previous = getattr(instance, "_ym_previous_fields", None)
    if not previous:
        return
    changed = {key for key in PRODUCT_FIELDS if previous[key] != getattr(instance, key) and (not update_fields or key in update_fields)}
    if not changed:
        return
    for connection in OfferConnection.objects.filter(active=True, managed=True, **{kind: instance}).select_related("remote_offer"):
        content, dirty = dict(connection.content), set(connection.dirty_fields)
        if connection.remote_offer.card_status != "HAS_CARD_CAN_NOT_UPDATE":
            for source, target in (("name", "name"), ("description", "description"), ("sku", "vendorCode")):
                if source in changed and getattr(instance, source):
                    content[target] = getattr(instance, source)
                    dirty.add(target)
            if "weight_grams" in changed:
                dimensions = content.get("weightDimensions") or connection.remote_offer.snapshot.get("offer", {}).get("weightDimensions")
                if dimensions:
                    content["weightDimensions"] = dimensions
                    dirty.add("weightDimensions")
        OfferConnection.objects.filter(pk=connection.pk).update(content=content, dirty_fields=sorted(dirty), revision=F("revision") + 1)
        product_after_commit(connection.pk)
