"""Пересчёт рекомендации не изменяет опубликованную цену и не ставит API-задачи."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from catalog.models import CD, Tech
from .models import CategorySchema, Integration, OfferConnection, RemoteOffer
from .fbs_pricing import INPUT_FIELDS, refresh_recommendation, refresh_recommendations

FIELDS = ("cost", *INPUT_FIELDS)


@receiver(pre_save, sender=CD, dispatch_uid="fbs_cd_before")
@receiver(pre_save, sender=Tech, dispatch_uid="fbs_tech_before")
def remember_inputs(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields and not set(update_fields).intersection(FIELDS)):
        return
    instance._fbs_before = sender.objects.filter(pk=instance.pk).values(*FIELDS).first() if instance.pk else None


@receiver(post_save, sender=CD, dispatch_uid="fbs_cd_after")
@receiver(post_save, sender=Tech, dispatch_uid="fbs_tech_after")
def inputs_changed(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields and not set(update_fields).intersection(FIELDS)):
        return
    before = getattr(instance, "_fbs_before", None)
    changed = not before or any(before[name] != getattr(instance, instance._meta.get_field(name).attname) for name in FIELDS)
    if changed and (instance.yandex_desired_profit is not None or instance.yandex_calculated_price is not None):
        refresh_recommendation(instance)


@receiver(pre_save, sender=Integration, dispatch_uid="fbs_settings_before")
def remember_settings(sender, instance, **kwargs):
    previous = sender.objects.filter(pk=instance.pk).values_list("configuration", flat=True).first() if instance.pk else None
    instance._fbs_previous_configuration = (previous or {}).get("fbs_pricing")


@receiver(post_save, sender=Integration, dispatch_uid="fbs_settings_after")
def settings_changed(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, "_fbs_previous_configuration", None) != (instance.configuration or {}).get("fbs_pricing"):
        refresh_recommendations(integration_id=instance.pk)


@receiver(pre_save, sender=CategorySchema, dispatch_uid="fbs_category_before")
def remember_rate(sender, instance, **kwargs):
    instance._fbs_previous_rate = sender.objects.filter(pk=instance.pk).values_list("placement_rate", flat=True).first() if instance.pk else None


@receiver(post_save, sender=CategorySchema, dispatch_uid="fbs_category_after")
def rate_changed(sender, instance, raw=False, **kwargs):
    if not raw and getattr(instance, "_fbs_previous_rate", None) != instance.placement_rate:
        refresh_recommendations(category_id=instance.category_id)


@receiver(post_save, sender=OfferConnection, dispatch_uid="fbs_connection_after")
def connection_changed(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields and not set(update_fields).intersection({"category_id", "active", "cd", "tech", "integration"})):
        return
    product = instance.product
    if product.yandex_desired_profit is not None:
        refresh_recommendation(product)


@receiver(pre_save, sender=RemoteOffer, dispatch_uid="fbs_remote_category_before")
def remember_remote_category(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields and "category_id" not in update_fields):
        return
    instance._fbs_previous_category = sender.objects.filter(pk=instance.pk).values_list("category_id", flat=True).first() if instance.pk else None


@receiver(post_save, sender=RemoteOffer, dispatch_uid="fbs_remote_category_after")
def remote_category_changed(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or (update_fields and "category_id" not in update_fields):
        return
    if getattr(instance, "_fbs_previous_category", None) == instance.category_id:
        return
    for connection in instance.connections.filter(active=True, category_id__isnull=True).select_related("cd", "tech"):
        product = connection.product
        if not product.is_archived and product.yandex_desired_profit is not None:
            refresh_recommendation(product)
