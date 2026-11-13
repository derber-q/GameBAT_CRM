"""Внешняя авторизация и доставка документов; склад и деньги принадлежат sales."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class BotConfig(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField('Включён', default=False)
    accepting_orders = models.BooleanField('Приём заказов включён', default=True)
    service_revision = models.PositiveIntegerField(default=1, editable=False)
    username = models.CharField('Username бота', max_length=64, default='ReSOURCE_OPT_BOT')
    warehouse = models.ForeignKey('warehouse.Warehouse', null=True, on_delete=models.PROTECT, verbose_name='Склад')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, verbose_name='Сотрудник операций')
    next_update_id = models.BigIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name='opt_single_config')]
        permissions = [('configure_wholesale_bot', 'Настройка оптового Telegram-бота')]


class Customer(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Не подал заявку'
        PENDING = 'pending', 'Ожидает авторизации'
        AUTHORIZED = 'authorized', 'Авторизован'
        REJECTED = 'rejected', 'Отклонён'
        REVOKED = 'revoked', 'Доступ отозван'

    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True)
    first_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    partner = models.ForeignKey('partners.Partner', null=True, blank=True, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=1)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [('manage_wholesale_customers', 'Управление покупателями оптового Telegram-бота')]
        constraints = [models.CheckConstraint(condition=Q(telegram_id__gt=0), name='opt_customer_positive_id'),
            models.CheckConstraint(condition=~Q(status='authorized') | Q(partner__isnull=False), name='opt_authorized_partner')]

    def __str__(self):
        return f'{self.first_name} {self.last_name} · {self.telegram_id}'.strip()


class PriceIssue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    partner = models.ForeignKey('partners.Partner', on_delete=models.PROTECT)
    customer_revision = models.PositiveIntegerField()
    warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.PROTECT)
    content = models.BinaryField(editable=False)
    manifest = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class OrderIntent(models.Model):
    class State(models.TextChoices):
        RECEIVED = 'received', 'Файл принят'
        INVALID = 'invalid', 'Некорректный файл'
        SHORTAGE = 'shortage', 'Недостаточно товаров'
        PRICES = 'prices', 'Ожидает подтверждения цен'
        DUPLICATE = 'duplicate', 'Требует подтверждения повторного заказа'
        CANCELLED = 'cancelled', 'Оформление отменено'
        CREATED = 'created', 'Продажа создана'
        FAILED = 'failed', 'Требует проверки'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    partner = models.ForeignKey('partners.Partner', on_delete=models.PROTECT)
    customer_revision = models.PositiveIntegerField()
    issue = models.ForeignKey(PriceIssue, null=True, on_delete=models.PROTECT)
    message_id = models.BigIntegerField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.RECEIVED, db_index=True)
    content = models.BinaryField(editable=False)
    lines = models.JSONField(default=list)
    quote = models.JSONField(default=list)
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    revision = models.PositiveIntegerField(default=1)
    repeat_allowed = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    sale = models.OneToOneField('sales.Sale', null=True, blank=True, on_delete=models.PROTECT, related_name='wholesale_telegram_order')
    error = models.TextField(blank=True)
    price_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['customer', 'message_id'], name='opt_customer_document_once')]

    @property
    def display_state(self):
        # Штатная отмена Sale остаётся источником истины; отдельный второй статус не нужен.
        if self.sale_id and self.sale.is_cancelled:
            return 'Продажа отменена'
        return self.get_state_display()


class Event(models.Model):
    """Долговечный inbox: offset подтверждается вместе с сохранением события."""
    update_id = models.BigIntegerField(unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    payload = models.JSONField(default=dict)
    state = models.CharField(max_length=16, default='pending', db_index=True)
    error = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Delivery(models.Model):
    """Отправка не входит в транзакцию Sale. Неизвестный результат требует решения."""
    key = models.CharField(max_length=180, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    customer_revision = models.PositiveIntegerField()
    intent = models.ForeignKey(OrderIntent, null=True, blank=True, on_delete=models.PROTECT)
    issue = models.ForeignKey(PriceIssue, null=True, blank=True, on_delete=models.PROTECT)
    text = models.TextField(blank=True)
    markup = models.JSONField(default=dict)
    document = models.BinaryField(null=True, editable=False)
    filename = models.CharField(max_length=180, blank=True)
    requires_authorization = models.BooleanField(default=True)
    state = models.CharField(max_length=16, default='pending', db_index=True)
    error = models.CharField(max_length=80, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)


class Audit(models.Model):
    customer = models.ForeignKey(Customer, null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
