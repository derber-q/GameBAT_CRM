"""Предзагрузка ярлыков без печати; освобождение PDF после завершения заказа."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from sales.models import Sale, MarketPrintJob
from .models import OrderMetadata
from .documents import request_labels

FINAL_PRINT_STATES = ('done', 'error', 'uncertain')
TERMINAL_ORDER_STATES = ('CANCELLED', 'DELIVERED', 'RETURNED', 'PARTIALLY_RETURNED')


def maintain_label_cache(order_id):
    order = OrderMetadata.objects.select_related('integration__operator', 'sale').filter(pk=order_id).first()
    if not order or not order.sale_id or order.fake:
        return
    terminal = order.status in TERMINAL_ORDER_STATES or order.sale.is_cancelled or order.sale.is_completed
    if terminal:
        # Даже завершение заказа не должно удалять PDF из-под активной печати.
        if order.print_jobs.exclude(state__in=FINAL_PRINT_STATES).exists():
            return
        for document in order.labels.exclude(cache_signature='').exclude(state='expired'):
            if document.file:
                document.file.delete(save=False)
            document.state = 'expired'
            document.save(update_fields=['file', 'state'])
        return
    if (not order.integration.enabled or order.status not in ('PROCESSING', 'DELIVERY', 'PICKUP')
            or not order.integration.operator.has_perm('yandex_market.print_labels')):
        return
    return request_labels(integration=order.integration, orders=[order], actor=order.integration.operator,
                          format_name='A9_HORIZONTALLY', reuse=True)


def schedule_label_cache(order_id):
    # Сбой подготовки PDF не отменяет продажу и не теряет уведомление о заказе.
    transaction.on_commit(lambda: maintain_label_cache(order_id), robust=True)


@receiver(post_save, sender=OrderMetadata, dispatch_uid='ym_order_label_cache')
def order_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        schedule_label_cache(instance.pk)


@receiver(post_save, sender=Sale, dispatch_uid='ym_sale_label_cleanup')
def sale_saved(sender, instance, raw=False, **kwargs):
    if not raw and instance.sale_type == 'yandex_market' and (instance.is_cancelled or instance.is_completed):
        for order_id in OrderMetadata.objects.filter(sale=instance).values_list('pk', flat=True):
            schedule_label_cache(order_id)


@receiver(post_save, sender=MarketPrintJob, dispatch_uid='ym_print_label_cleanup')
def print_saved(sender, instance, raw=False, **kwargs):
    if not raw and instance.state in FINAL_PRINT_STATES:
        schedule_label_cache(instance.order_id)
