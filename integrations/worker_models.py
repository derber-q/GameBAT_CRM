"""Технические состояния процессов; не связаны с товарным и денежным учётом."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


SERVICE_CHOICES = [('avito', 'Avito'), ('yandex', 'Яндекс Маркет'),
                   ('google', 'Google Sheets'), ('print', 'Печать этикеток'),
                   ('telegram_staff', 'Telegram — сотрудники')]


class WorkerController(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    mode = models.CharField(max_length=16, default='site_only', choices=[
        ('site_only', 'Только сайт'), ('managed', 'Контроль включён')])
    instance = models.UUIDField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    incident = models.UUIDField(default=uuid.uuid4)
    incident_started_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name='single_worker_controller')]


class WorkerProcess(models.Model):
    instance = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pid = models.PositiveIntegerField()
    birth = models.CharField(max_length=80)
    services = models.JSONField(default=list)
    heartbeat_at = models.DateTimeField(db_index=True)
    ready = models.BooleanField(default=False)
    action = models.CharField(max_length=32, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)


class WorkerService(models.Model):
    code = models.CharField(primary_key=True, max_length=20, choices=SERVICE_CHOICES)
    expected = models.CharField(max_length=20, default='unconfigured')
    status = models.CharField(max_length=20, default='unknown')
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    observed_at = models.DateTimeField(null=True, blank=True)
    incident = models.UUIDField(null=True, blank=True)
    incident_started_at = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)
    auto_paused = models.BooleanField(default=False)
    launch_instance = models.UUIDField(null=True, blank=True)
    launch_started_at = models.DateTimeField(null=True, blank=True)
    stable_since = models.DateTimeField(null=True, blank=True)
    stable_instance = models.UUIDField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=40, blank=True)


class WorkerCommand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.UUIDField()
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    state = models.CharField(max_length=16, default='queued')
    result = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['request_id', 'service'], name='worker_request_service'),
            models.UniqueConstraint(fields=['service'], condition=Q(state__in=['queued', 'running']),
                                    name='worker_one_active_command'),
        ]


class WorkerEvent(models.Model):
    service = models.CharField(max_length=16, blank=True)
    kind = models.CharField(max_length=40)
    result = models.CharField(max_length=40, blank=True)
    incident = models.UUIDField(null=True, blank=True)
    command = models.ForeignKey(WorkerCommand, null=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-id']
