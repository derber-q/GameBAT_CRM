"""Отдельная идентичность локального устройства печати, без прав пользователя CRM."""
import uuid
from django.db import models


class PrintAgent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    printer_name = models.CharField(max_length=200)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    enabled = models.BooleanField(default=True)
    session = models.UUIDField(null=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, editable=False)
    printer_available = models.BooleanField(null=True, editable=False)
    version = models.CharField(max_length=32, blank=True, editable=False)
    last_error = models.CharField(max_length=200, blank=True, editable=False)
    incident = models.UUIDField(null=True, editable=False)
    incident_started_at = models.DateTimeField(null=True, editable=False)

    def __str__(self):
        return self.name
