"""Цифровые заказы и журналы предоплаты; физическая номенклатура не используется."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q

RETAIL_LABEL = 'Розничный покупатель'


class Buyer(models.Model):
    name = models.CharField('Покупатель', max_length=160)
    partner = models.ForeignKey('partners.Partner', null=True, blank=True, on_delete=models.PROTECT)
    contact = models.CharField('Контакт', max_length=160, blank=True)
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'pk']

    def __str__(self):
        return self.name

    @property
    def balance(self):
        return self.movements.aggregate(total=models.Sum('delta'))['total'] or Decimal('0.00')


class Supplier(models.Model):
    name = models.CharField('Поставщик', max_length=160, unique=True)
    chat_ids = models.JSONField('Разрешённые chat ID', default=list)
    sender_ids = models.JSONField('Разрешённые ID отправителей', default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def balance(self):
        return self.movements.aggregate(total=models.Sum('delta'))['total'] or Decimal('0.00')


class DigitalBot(models.Model):
    """Собственный offset/аренда: не конкурирует с получателем бота сотрудников."""
    singleton = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField('Включён', default=False)
    username = models.CharField(max_length=64, default='ReSOURSE_digital_goods_BOT')
    next_update_id = models.BigIntegerField(default=0)
    lease_owner = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    last_poll_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)
    bot_messages = models.PositiveIntegerField(default=0)
    human_messages = models.PositiveIntegerField(default=0)
    forwarded_messages = models.PositiveIntegerField(default=0)
    last_chat_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(singleton=1), name='digital_single_bot')]


class DigitalOrder(models.Model):
    class State(models.TextChoices):
        CHECKLIST = 'checklist', 'Ожидает чек-лист'
        GOODS = 'goods', 'Ожидает готовности'
        REVIEW = 'review', 'Требует проверки'
        READY = 'ready', 'Ожидает оформления'
        SALE = 'sale', 'Продажа создана'
        COMPLETED = 'completed', 'Продажа завершена'
        CANCELLED = 'cancelled', 'Продажа отменена'

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='orders')
    buyer = models.ForeignKey(Buyer, null=True, blank=True, on_delete=models.PROTECT, verbose_name='Покупатель')
    is_retail = models.BooleanField('Розничный покупатель без баланса', default=False)
    sale = models.OneToOneField('sales.Sale', null=True, blank=True, on_delete=models.PROTECT, related_name='digital_order')
    source = models.CharField(max_length=16, default='telegram', choices=[('telegram', 'Telegram'), ('manual', 'Создана вручную'), ('api_v2', 'Магазин API v2')])
    state = models.CharField(max_length=16, choices=State.choices, default=State.CHECKLIST, db_index=True)
    items = models.JSONField(default=list)
    cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    price = models.DecimalField('Общая цена продажи', max_digits=20, decimal_places=2, null=True, blank=True)
    checklist_received = models.BooleanField(default=False)
    goods_received = models.BooleanField(default=False)
    review_reason = models.CharField(max_length=300, blank=True)
    revision = models.PositiveIntegerField(default=1)
    comment = models.TextField('Комментарий', blank=True)
    source_url = models.URLField('Источник', blank=True)
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ignored_at = models.DateTimeField(null=True, blank=True)
    ignored_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    creation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        permissions = [
            ('view_digital_sales', 'Просмотр цифровых продаж'),
            ('create_digital_sales', 'Создание цифровых продаж'),
            ('telegram_digital_sales', 'Оформление цифровых продаж через Telegram'),
            ('complete_digital_sales', 'Завершение цифровых продаж'),
            ('cancel_digital_sales', 'Отмена цифровых продаж'),
            ('manage_digital_buyers', 'Управление цифровыми покупателями'),
            ('topup_digital_balances', 'Пополнение цифровых балансов'),
            ('adjust_digital_balances', 'Корректировка цифровых балансов'),
            ('view_digital_secrets', 'Просмотр защищённых данных цифровых товаров'),
            ('view_digital_reconciliation', 'Просмотр сверки цифрового поставщика'),
            ('configure_digital_bot', 'Настройка цифрового бота'),
        ]
        constraints = [models.CheckConstraint(condition=Q(cost__gte=0) & (Q(price__isnull=True) | Q(price__gt=0)), name='digital_order_money'),
                      models.CheckConstraint(condition=~Q(is_retail=True) | Q(buyer__isnull=True), name='digital_retail_no_wallet')]

    @property
    def customer_display_name(self):
        return RETAIL_LABEL if self.is_retail else self.buyer.name if self.buyer_id else 'Не выбран'

    @property
    def processing_stopped(self):
        return bool(self.ignored_at or self.state == self.State.CANCELLED)


class OrderReference(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    order = models.ForeignKey(DigitalOrder, on_delete=models.PROTECT, related_name='references')
    number = models.CharField(max_length=40)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['supplier', 'number'], name='digital_supplier_order_number')]


class BalanceMovement(models.Model):
    """Один адресат, signed delta; сторно связано с исходной неизменяемой записью."""
    buyer = models.ForeignKey(Buyer, null=True, blank=True, on_delete=models.PROTECT, related_name='movements')
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name='movements')
    sale = models.ForeignKey('sales.Sale', null=True, blank=True, on_delete=models.PROTECT, related_name='digital_movements')
    delta = models.DecimalField(max_digits=20, decimal_places=2)
    kind = models.CharField(max_length=16, choices=[('opening', 'Начальный остаток'), ('topup', 'Пополнение'), ('sale', 'Списание за продажу'), ('reversal', 'Сторно'), ('adjustment', 'Корректировка')])
    operation_key = models.UUIDField(default=uuid.uuid4, unique=True)
    reversal_of = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal')
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']
        constraints = [
            models.CheckConstraint(condition=(Q(buyer__isnull=False, supplier__isnull=True) | Q(buyer__isnull=True, supplier__isnull=False)), name='digital_movement_one_owner'),
            models.CheckConstraint(condition=~Q(delta=0), name='digital_movement_nonzero'),
            models.UniqueConstraint(fields=['sale', 'buyer'], condition=Q(kind='sale'), name='digital_buyer_sale_once'),
            models.UniqueConstraint(fields=['sale', 'supplier'], condition=Q(kind='sale'), name='digital_supplier_sale_once'),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            from django.core.exceptions import ValidationError
            raise ValidationError('Движения неизменяемы; используйте сторно.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('История балансов не удаляется.')


class SupplierMessage(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    order = models.ForeignKey(DigitalOrder, null=True, blank=True, on_delete=models.PROTECT, related_name='messages')
    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    edit_version = models.BigIntegerField(default=0)
    sender_id = models.BigIntegerField(null=True)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    forwarded = models.BooleanField(default=False)
    kind = models.CharField(max_length=16)
    fingerprint = models.CharField(max_length=64)
    encrypted_payload = models.TextField()
    parsed = models.JSONField(default=dict)
    attachment_state = models.CharField(max_length=16, default='none')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['chat_id', 'message_id', 'edit_version'], name='digital_message_version')]


class SupplierPurchase(models.Model):
    order = models.OneToOneField(DigitalOrder, on_delete=models.PROTECT, related_name='purchase')
    message = models.ForeignKey(SupplierMessage, null=True, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    occurred_at = models.DateTimeField()
    superseded_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='+')


class BalanceObservation(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='observations')
    message = models.OneToOneField(SupplierMessage, on_delete=models.PROTECT)
    balance = models.DecimalField(max_digits=20, decimal_places=2)
    expected = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    difference = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    uncertain = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(max_length=500, blank=True)
    credits_snapshot = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    purchases_snapshot = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    topup_movement = models.OneToOneField(BalanceMovement, null=True, blank=True, on_delete=models.PROTECT)


class AuditEvent(models.Model):
    order = models.ForeignKey(DigitalOrder, null=True, blank=True, on_delete=models.PROTECT, related_name='audit')
    message = models.ForeignKey(SupplierMessage, null=True, blank=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    kind = models.CharField(max_length=40)
    detail = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    """Outbox не содержит паролей; сетевой результат отделён от бизнес-транзакции."""
    order = models.ForeignKey(DigitalOrder, null=True, blank=True, on_delete=models.PROTECT)
    observation = models.ForeignKey(BalanceObservation, null=True, blank=True, on_delete=models.PROTECT)
    access = models.ForeignKey('telegram_bots.StaffBotAccess', on_delete=models.PROTECT)
    event_key = models.CharField(max_length=100)
    text = models.TextField()
    state = models.CharField(max_length=16, default='queued')
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['access', 'event_key'], name='digital_notification_once')]


class StaffConversation(models.Model):
    access = models.OneToOneField('telegram_bots.StaffBotAccess', on_delete=models.CASCADE)
    order = models.ForeignKey(DigitalOrder, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    field = models.CharField(max_length=16)
    expires_at = models.DateTimeField()


class BuyerBalanceChat(models.Model):
    """Только явно выбранная группа получает баланс одного цифрового покупателя."""
    chat_id = models.BigIntegerField(primary_key=True)
    title = models.CharField(max_length=255)
    buyer = models.OneToOneField(Buyer, null=True, blank=True, on_delete=models.PROTECT, related_name='balance_chat')
    can_pin = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    message_id = models.BigIntegerField(null=True, blank=True)
    message_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(chat_id__lt=0), name='digital_balance_group_only')]

    def __str__(self):
        return f'{self.title} ({self.chat_id})'


class BalanceChatCommand(models.Model):
    update_id = models.BigIntegerField(unique=True)
    chat = models.ForeignKey(BuyerBalanceChat, on_delete=models.PROTECT)
    sender_id = models.BigIntegerField()
    buyer_id_requested = models.PositiveBigIntegerField()
    state = models.CharField(max_length=16, default='queued')
    error_category = models.CharField(max_length=40, blank=True)


class BalanceChatPublication(models.Model):
    """Сеть вне учёта; отдельное сообщение на событие, старые ID сохранены для истории."""
    chat = models.ForeignKey(BuyerBalanceChat, on_delete=models.PROTECT, related_name='publications')
    buyer = models.ForeignKey(Buyer, on_delete=models.PROTECT)
    event_key = models.CharField(max_length=120, unique=True)
    state = models.CharField(max_length=16, default='queued')
    stage = models.CharField(max_length=16, default='send')
    text = models.TextField(blank=True)
    message_id = models.BigIntegerField(null=True, blank=True)
    copy_message_id = models.BigIntegerField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
