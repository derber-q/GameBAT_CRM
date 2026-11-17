"""Внутренний стикер продажи использует прежний протокол агента печати."""
import uuid
from django.conf import settings
from django.db import models


class SaleLabelPrintJob(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, unique=True)
    sale = models.ForeignKey('sales.Sale', on_delete=models.PROTECT, related_name='label_print_jobs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    file = models.FileField(upload_to='sale_labels/%Y/%m/')
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

    class Meta:
        verbose_name = 'печать внутреннего стикера продажи'
        verbose_name_plural = 'печать внутренних стикеров продаж'
