from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from catalog.models import CD, Tech

from .models import CDWarehouseStock, TechWarehouseStock, WarehouseRevisionItem


def _refresh_zero_stock_marker(*, product_model, product_id):
    product = product_model.objects.filter(pk=product_id).only("zero_stock_since").first()
    if product is None:
        return
    total = product.warehouse_stocks.aggregate(total=Sum("quantity"))["total"] or 0
    if total > 0 and product.zero_stock_since is not None:
        product_model.objects.filter(pk=product_id).update(zero_stock_since=None)
    elif total == 0 and product.zero_stock_since is None:
        product_model.objects.filter(pk=product_id).update(zero_stock_since=timezone.now())


@receiver(post_save, sender=CDWarehouseStock)
@receiver(post_delete, sender=CDWarehouseStock)
def refresh_cd_zero_stock_since(sender, instance, **kwargs):
    _refresh_zero_stock_marker(product_model=CD, product_id=instance.cd_id)


@receiver(post_save, sender=TechWarehouseStock)
@receiver(post_delete, sender=TechWarehouseStock)
def refresh_tech_zero_stock_since(sender, instance, **kwargs):
    _refresh_zero_stock_marker(product_model=Tech, product_id=instance.tech_id)


def _invalidate_revision_check(instance, *, deleted=False):
    if not deleted and instance.quantity > 0:
        return
    kind = "cd" if isinstance(instance, CDWarehouseStock) else "tech"
    # Отметка остаётся в истории, но возвращённый после обнуления товар
    # требует повторной проверки. Физические остатки этот UPDATE не меняет.
    WarehouseRevisionItem.objects.filter(
        revision__warehouse_id=instance.warehouse_id, revision__is_active=True,
        invalidated_at__isnull=True, **{f"{kind}_id": getattr(instance, f"{kind}_id")},
    ).update(invalidated_at=timezone.now())


@receiver(post_save, sender=CDWarehouseStock)
@receiver(post_save, sender=TechWarehouseStock)
def invalidate_revision_on_zero(sender, instance, raw=False, **kwargs):
    if not raw:
        _invalidate_revision_check(instance)


@receiver(post_delete, sender=CDWarehouseStock)
@receiver(post_delete, sender=TechWarehouseStock)
def invalidate_revision_on_delete(sender, instance, **kwargs):
    _invalidate_revision_check(instance, deleted=True)
