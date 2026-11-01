"""Ссылка на заказ Avito и очередь печати, независимые от браузерной вкладки."""
import uuid
from django.conf import settings
from django.db import models


class AvitoBrowserOrder(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    titles = models.JSONField(default=list)
    carrier = models.CharField(max_length=100, blank=True)
    displayed_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    sale = models.OneToOneField('sales.Sale', on_delete=models.PROTECT, null=True, related_name='avito_browser_order')
    creation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AvitoShippingPrintJob(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, unique=True)
    order = models.ForeignKey(AvitoBrowserOrder, on_delete=models.PROTECT, related_name='print_jobs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(upload_to='avito_shipping/%Y/%m/')
    document_digest = models.CharField(max_length=64)
    state = models.CharField(max_length=24, default='pending')
    print_backend = models.CharField(max_length=12, default='native')
    printer_name = models.CharField(max_length=200)
    agent = models.ForeignKey('sales.PrintAgent', on_delete=models.PROTECT, null=True)
    agent_claim = models.UUIDField(null=True)
    agent_claimed_at = models.DateTimeField(null=True)
    printer_job_id = models.PositiveIntegerField(null=True)
    spooled_at = models.DateTimeField(null=True)
    printed_at = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
