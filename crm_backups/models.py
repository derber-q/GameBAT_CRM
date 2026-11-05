"""Технические задания, отдельно от денег, склада и механизма обновлений."""
import datetime
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

ACTIVE = ('queued', 'snapshot', 'files', 'checking', 'encrypting')


class BackupConfiguration(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    environment_id = models.UUIDField(default=uuid.uuid4, editable=False)
    enabled = models.BooleanField(default=False)
    public_key = models.TextField(blank=True)
    recovery_key_saved = models.BooleanField(default=False)
    schedule_time = models.TimeField(default=datetime.time(3, 0))
    timezone = models.CharField(max_length=64, default='Europe/Moscow')
    last_schedule_day = models.DateField(null=True, editable=False)
    max_pending = models.PositiveSmallIntegerField(default=2)
    retention_days = models.PositiveSmallIntegerField(default=2)
    last_worker_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name='backup_single_configuration')]


class BackupJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.UUIDField(unique=True)
    active_slot = models.PositiveSmallIntegerField(null=True, default=1, editable=False)
    kind = models.CharField(max_length=16, default='manual')
    state = models.CharField(max_length=16, default='queued', db_index=True)
    scheduled_for = models.DateField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    downloaded_at = models.DateTimeField(null=True)
    key_id = models.CharField(max_length=64, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    metadata = models.JSONField(default=dict)
    error = models.CharField(max_length=80, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['active_slot'], name='backup_one_active_job'),
            models.CheckConstraint(condition=(Q(state__in=ACTIVE, active_slot=1) |
                (~Q(state__in=ACTIVE) & Q(active_slot__isnull=True))), name='backup_slot_matches_state'),
        ]


class BackupEvent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    job = models.ForeignKey(BackupJob, on_delete=models.SET_NULL, null=True)
    details = models.JSONField(default=dict)


class BackupDevice(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    name = models.CharField(max_length=120)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    active_slot = models.PositiveSmallIntegerField(null=True, default=1, unique=True, editable=False)
    can_request = models.BooleanField(default=False)
    session = models.UUIDField(null=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, editable=False)
    version = models.CharField(max_length=32, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(active_slot=1) | Q(active_slot__isnull=True), name='backup_device_one_slot')]


class BackupEnrollment(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    replace = models.BooleanField(default=False)
    can_request = models.BooleanField(default=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class PrintRouting(models.Model):
    """Явное административное назначение; прежние задания хранят свою цель."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    default_agent = models.ForeignKey('sales.PrintAgent', on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name='print_routing_singleton')]


class ApplicationArtifact(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=16,choices=[('local_agent','Local Agent'),('opera','Opera GX')])
    version=models.CharField(max_length=32)
    sha256=models.CharField(max_length=64)
    size=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(auto_now_add=True)
    current=models.BooleanField(default=True)
    notes=models.TextField(blank=True)
    metadata=models.JSONField(default=dict)
    published_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

    class Meta:
        permissions=[('download_client_apps','Скачивание локальных приложений и расширений')]
        constraints=[models.UniqueConstraint(fields=['kind'],condition=Q(current=True),name='one_current_client_artifact')]
