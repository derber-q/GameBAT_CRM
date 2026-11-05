"""Одноразовое подключение и отзыв: отдельный секрет, не токен принтера."""
from datetime import timedelta
import hashlib
import re
import secrets
import uuid
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from core.external_policy import require_live_operation
from .jobs import locked_config, audit
from .models import BackupDevice, BackupEnrollment


def administrator(actor):
    if not actor or not actor.is_active or not actor.is_superuser:
        raise PermissionError('Доступно только суперпользователю.')


@retry_database_lock
@transaction.atomic
def issue_enrollment(actor, *, replace=False, can_request=False):
    require_live_operation('backup_enrollment')
    administrator(actor); locked_config()
    if BackupDevice.objects.filter(active_slot=1).exists() and not replace:
        raise ValueError('Устройство уже подключено. Для замены требуется отдельное подтверждение.')
    # Ранее выданные неиспользованные операции аннулируются без раскрытия кода.
    for item in BackupEnrollment.objects.filter(consumed_at__isnull=True):
        item.consumed_at=timezone.now(); item.save(update_fields=['consumed_at'])
    code = secrets.token_urlsafe(32)
    BackupEnrollment.objects.create(digest=hashlib.sha256(code.encode()).hexdigest(),
        expires_at=timezone.now()+timedelta(minutes=10), replace=replace, can_request=can_request, actor=actor)
    audit('device_enrollment_issued', actor=actor, replace=replace)
    return code


@retry_database_lock
@transaction.atomic
def enroll(code, device_id, token_hash, name):
    require_live_operation('backup_enroll')
    locked_config()
    if not isinstance(code,str) or len(code)>128 or not re.fullmatch('[a-f0-9]{64}',token_hash) or not 1<=len(name)<=120:
        raise ValueError('Некорректная регистрация.')
    device_id=uuid.UUID(str(device_id))
    operation=BackupEnrollment.objects.select_for_update().filter(digest=hashlib.sha256(code.encode()).hexdigest(),
        consumed_at__isnull=True, expires_at__gt=timezone.now()).first()
    if not operation: raise ValueError('Код недействителен или использован.')
    administrator(operation.actor)
    if BackupDevice.objects.filter(pk=device_id).exists(): raise ValueError('Идентификатор уже использован.')
    previous=BackupDevice.objects.filter(active_slot=1).first()
    if previous:
        if not operation.replace: raise ValueError('Другой получатель уже подключён.')
        previous.active_slot=None; previous.revoked_at=timezone.now(); previous.save(update_fields=['active_slot','revoked_at'])
        audit('device_replaced',actor=operation.actor, device=str(previous.pk))
    operation.consumed_at=timezone.now(); operation.save(update_fields=['consumed_at'])
    device=BackupDevice.objects.create(pk=device_id,name=name,token_hash=token_hash,can_request=operation.can_request)
    audit('device_enrolled',actor=operation.actor, device=str(device.pk))
    return device


@retry_database_lock
@transaction.atomic
def revoke(actor, device_id):
    require_live_operation('backup_revoke'); administrator(actor); locked_config()
    device=BackupDevice.objects.select_for_update().get(pk=device_id)
    device.active_slot=None; device.revoked_at=timezone.now(); device.save(update_fields=['active_slot','revoked_at'])
    audit('device_revoked',actor=actor,device=str(device.pk))
