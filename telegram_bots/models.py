"""Только конфигурация, доступ и техническая очередь; товары и деньги не изменяются."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class StaffBot(models.Model):
    code = models.CharField(max_length=32, unique=True, default='staff', editable=False)
    name = models.CharField(max_length=100, default='ReSOURCE | Сотрудники')
    username = models.CharField(max_length=32, blank=True)
    enabled = models.BooleanField(default=False)
    cooldown_seconds = models.PositiveIntegerField(default=30)
    next_update_id = models.BigIntegerField(default=0)
    last_poll_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)
    # Межпроцессная блокировка ОС дополнена арендой в общей БД для будущего Linux.
    lease_owner = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'бот сотрудников'
        permissions = [('use_staff_bot', 'Может пользоваться Telegram-ботом сотрудников')]


class StaffBotAccess(models.Model):
    bot = models.ForeignKey(StaffBot, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    allowed = models.BooleanField(default=False)
    telegram_user_id = models.BigIntegerField(null=True, blank=True)
    username = models.CharField(max_length=64, blank=True)
    linked_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['bot', 'user'], name='telegram_bot_employee'),
            models.UniqueConstraint(fields=['bot', 'telegram_user_id'], name='telegram_bot_identity'),
        ]


class StaffBotLink(models.Model):
    access = models.ForeignKey(StaffBotAccess, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StaffBotUpdate(models.Model):
    bot = models.ForeignKey(StaffBot, on_delete=models.CASCADE)
    update_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['bot', 'update_id'], name='telegram_bot_update')]


class StaffBotJob(models.Model):
    class State(models.TextChoices):
        QUEUED = 'queued', 'В очереди'
        GENERATING = 'generating', 'Формируется'
        SENDING = 'sending', 'Отправляется'
        DONE = 'done', 'Отправлен'
        ERROR = 'error', 'Ошибка'
        UNCERTAIN = 'uncertain', 'Результат отправки неизвестен'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bot = models.ForeignKey(StaffBot, on_delete=models.CASCADE)
    access = models.ForeignKey(StaffBotAccess, on_delete=models.PROTECT)
    warehouse = models.ForeignKey('warehouse.Warehouse', null=True, on_delete=models.SET_NULL)
    update = models.OneToOneField(StaffBotUpdate, on_delete=models.PROTECT)
    chat_id = models.BigIntegerField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        constraints = [models.UniqueConstraint(fields=['access'],
            condition=Q(state__in=['queued', 'generating', 'sending']), name='telegram_one_active_price')]
