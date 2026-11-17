"""Корзины, резервы и состояние доставки; деньги остаются в digital_sales."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class ShopConfig(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False)
    purchases_enabled = models.BooleanField(default=False)
    supplier = models.ForeignKey('digital_sales.Supplier', null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    revision = models.PositiveBigIntegerField(default=0)
    write_revision = models.PositiveBigIntegerField(default=0)
    last_poll_at = models.DateTimeField(null=True)
    list_poll_at = models.DateTimeField(null=True)
    list_page = models.PositiveIntegerField(default=1)
    last_success_at = models.DateTimeField(null=True)
    error_category = models.CharField(max_length=40, blank=True)
    observed_balance = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    observed_at = models.DateTimeField(null=True)

    class Meta:
        permissions = [('manage_shop', 'Настройка и сверка цифрового магазина')]


class ShopChat(models.Model):
    binding = models.OneToOneField('digital_sales.BuyerBalanceChat', primary_key=True, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=False)


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey('digital_sales.Buyer', on_delete=models.PROTECT)
    chat = models.ForeignKey('digital_sales.BuyerBalanceChat', on_delete=models.PROTECT)
    telegram_user_id = models.BigIntegerField()  # Инициатор открытия; доступ определяется группой.
    revision = models.PositiveIntegerField(default=1)
    state = models.CharField(max_length=20, default='open')
    menu_message_id = models.BigIntegerField(null=True)
    search_query = models.CharField(max_length=150, blank=True)
    search_product_ids = models.JSONField(default=list)
    search_platform = models.CharField(max_length=20, default='playstation')
    search_region = models.CharField(max_length=80, blank=True)
    input_kind = models.CharField(max_length=20, blank=True)
    input_product = models.ForeignKey('digital_prices.Product', null=True, on_delete=models.PROTECT)
    input_mode = models.CharField(max_length=12, blank=True)
    input_account = models.CharField(max_length=32, blank=True)
    prompt_message_id = models.BigIntegerField(null=True)
    encrypted_credentials = models.TextField(blank=True)
    quote_id = models.CharField(max_length=128, blank=True)
    quote_expires_at = models.DateTimeField(null=True)
    quote_revision = models.PositiveIntegerField(null=True)
    quoted_total = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    client_total = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    catalog_revision = models.PositiveBigIntegerField(default=0)
    price_snapshot = models.JSONField(default=dict)
    credential_groups = models.JSONField(default=list)
    quote_body = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['buyer', 'chat'],
            condition=~Q(state='closed'), name='shop_group_active_cart')]


class CartLine(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.PROTECT, related_name='lines')
    product = models.ForeignKey('digital_prices.Product', on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField(default=1)
    account_key = models.CharField(max_length=32, blank=True)
    account_mode = models.CharField(max_length=12, blank=True)
    parameters = models.JSONField(default=dict)


class PurchaseIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.OneToOneField(Cart, on_delete=models.PROTECT)
    client_order_id = models.CharField(max_length=64, unique=True)
    encrypted_body = models.TextField()
    body_hash = models.CharField(max_length=64)
    external_order_id = models.CharField(max_length=128, blank=True, db_index=True)
    state = models.CharField(max_length=20, default='queued', db_index=True)
    owner = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    next_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    error_category = models.CharField(max_length=40, blank=True)
    encrypted_response = models.TextField(blank=True)
    poll_fingerprint = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)


class BalanceHold(models.Model):
    intent = models.OneToOneField(PurchaseIntent, on_delete=models.PROTECT)
    buyer = models.ForeignKey('digital_sales.Buyer', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    remaining = models.DecimalField(max_digits=20, decimal_places=2)
    state = models.CharField(max_length=12, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(remaining__gte=0) & Q(amount__gt=0) & Q(remaining__lte=models.F('amount')), name='shop_hold_bounds')]


class PurchaseLine(models.Model):
    intent = models.ForeignKey(PurchaseIntent, on_delete=models.PROTECT, related_name='lines')
    cart_line = models.OneToOneField(CartLine, on_delete=models.PROTECT)
    line_id = models.CharField(max_length=32)
    purchase_id = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, default='waiting')
    cost = models.DecimalField(max_digits=20, decimal_places=2)
    confirmed_cost = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    client_price = models.DecimalField(max_digits=20, decimal_places=2)
    snapshot = models.JSONField(default=dict)
    digital_order = models.OneToOneField('digital_sales.DigitalOrder', null=True, on_delete=models.PROTECT)
    supplier_movement = models.OneToOneField('digital_sales.BalanceMovement', null=True, on_delete=models.PROTECT)
    encrypted_result = models.TextField(blank=True)
    settled_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['intent', 'line_id'], name='shop_intent_line_once')]


class ResultDelivery(models.Model):
    line = models.OneToOneField(PurchaseLine, on_delete=models.PROTECT)
    buyer = models.ForeignKey('digital_sales.Buyer', on_delete=models.PROTECT)
    chat_id = models.BigIntegerField()
    state = models.CharField(max_length=16, default='queued')
    encrypted_text = models.TextField()
    message_id = models.BigIntegerField(null=True)
    progress_index = models.PositiveSmallIntegerField(default=0)
    message_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)


class ConfirmedRefund(models.Model):
    line = models.OneToOneField(PurchaseLine, on_delete=models.PROTECT)
    movement = models.OneToOneField('digital_sales.BalanceMovement', null=True, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)


class ChatEvent(models.Model):
    update_id = models.BigIntegerField(primary_key=True)
    encrypted_payload = models.TextField()
    state = models.CharField(max_length=16, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    kind = models.CharField(max_length=40)
    intent = models.ForeignKey(PurchaseIntent, null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
