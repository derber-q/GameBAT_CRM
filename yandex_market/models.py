"""Данные Маркета отделены от номенклатуры, продаж и учётных остатков CRM."""
import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils import timezone


def json_field(**kwargs):
    return models.JSONField(encoder=DjangoJSONEncoder, **kwargs)


class Integration(models.Model):
    name = models.CharField("Название", max_length=200, default="Яндекс Маркет FBS")
    business_id = models.PositiveBigIntegerField("businessId", unique=True)
    campaign_id = models.PositiveBigIntegerField("campaignId", unique=True)
    partner_warehouse_id = models.PositiveBigIntegerField("Склад Маркета", null=True, blank=True)
    stock_api = models.CharField("API остатков", max_length=20, default="partner", choices=[("partner", "Склад кабинета (v3)"), ("group", "Группа складов (v2)")])
    price_scope = models.CharField("Область цены", max_length=20, default="business", choices=[("business", "Весь кабинет"), ("campaign", "Этот магазин")])
    fulfillment_warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.PROTECT, verbose_name="Склад выполнения заказов")
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Ответственный за автоматические операции")
    enabled = models.BooleanField("Фоновый обмен включён", default=False)
    import_orders_from = models.DateTimeField("Начало импорта заказов", default=timezone.now)
    checked_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    configuration = json_field(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("manage_settings", "Яндекс Маркет: настройки"),
            ("edit_content", "Яндекс Маркет: контент товаров"),
            ("bind_offer", "Яндекс Маркет: привязка товаров"),
            ("rebind_offer", "Яндекс Маркет: перепривязка и отвязка"),
            ("retry_sync", "Яндекс Маркет: синхронизация"),
            ("manage_orders", "Яндекс Маркет: обработка заказов"),
            ("print_labels", "Яндекс Маркет: печать ярлыков"),
            ("accept_return", "Яндекс Маркет: приём возврата"),
        ]

    def __str__(self):
        return self.name


class RemoteOffer(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT, related_name="offers")
    offer_id = models.CharField(max_length=255)
    name = models.CharField(max_length=512, blank=True)
    market_sku = models.PositiveBigIntegerField(null=True, blank=True)
    category_id = models.PositiveBigIntegerField(null=True, blank=True)
    category_name = models.CharField(max_length=512, blank=True)
    card_status = models.CharField(max_length=80, blank=True)
    content_rating = models.IntegerField(null=True, blank=True)
    snapshot = json_field(default=dict)
    card = json_field(default=dict)
    remote_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    remote_stock = models.PositiveIntegerField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(default=timezone.now)
    stock_checked_at = models.DateTimeField(null=True, blank=True)
    price_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["integration", "offer_id"], name="ym_unique_remote_offer")]
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name or self.offer_id} ({self.offer_id})"


class OfferConnection(models.Model):
    class State(models.TextChoices):
        LINKED = "linked", "Ожидает включения управления"
        QUEUED = "queued", "В очереди"
        SYNCING = "syncing", "Синхронизация"
        SYNCED = "synced", "Синхронизирован"
        ERROR = "error", "Ошибка"
        ATTENTION = "attention", "Требуется внимание"

    integration = models.ForeignKey(Integration, on_delete=models.PROTECT, related_name="connections")
    remote_offer = models.ForeignKey(RemoteOffer, on_delete=models.PROTECT, related_name="connections")
    cd = models.ForeignKey("catalog.CD", on_delete=models.PROTECT, null=True, blank=True, related_name="yandex_connections")
    tech = models.ForeignKey("catalog.Tech", on_delete=models.PROTECT, null=True, blank=True, related_name="yandex_connections")
    active = models.BooleanField(default=True)
    managed = models.BooleanField("Управление подтверждено", default=False)
    sell_on_yandex = models.BooleanField("Продаётся на Яндекс Маркете", default=False)
    is_new = models.BooleanField(default=False)
    content = json_field(default=dict, blank=True)
    dirty_fields = json_field(default=list, blank=True)
    delete_fields = json_field(default=list, blank=True)
    parameters = json_field(default=list, blank=True)
    category_id = models.PositiveBigIntegerField(null=True, blank=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.LINKED)
    revision = models.PositiveIntegerField(default=1)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    last_sent_hash = models.CharField(max_length=64, blank=True)
    last_sent_state = json_field(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(cd__isnull=False, tech__isnull=True) | Q(cd__isnull=True, tech__isnull=False)), name="ym_exactly_one_product"),
            models.UniqueConstraint(fields=["remote_offer"], condition=Q(active=True), name="ym_one_active_offer"),
            models.UniqueConstraint(fields=["integration", "cd"], condition=Q(active=True, cd__isnull=False), name="ym_one_active_cd"),
            models.UniqueConstraint(fields=["integration", "tech"], condition=Q(active=True, tech__isnull=False), name="ym_one_active_tech"),
        ]

    @property
    def product(self):
        return self.cd if self.cd_id else self.tech

    @property
    def product_kind(self):
        return "cd" if self.cd_id else "tech"


class CategorySchema(models.Model):
    category_id = models.PositiveBigIntegerField(unique=True)
    schema = json_field(default=dict)
    fetched_at = models.DateTimeField(default=timezone.now)


class Media(models.Model):
    connection = models.ForeignKey(OfferConnection, on_delete=models.PROTECT, related_name="media")
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    image = models.ImageField(upload_to="yandex/products/%Y/%m/")
    position = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]


class OrderMetadata(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT, related_name="orders")
    order_id = models.PositiveBigIntegerField()
    sale = models.OneToOneField("sales.Sale", on_delete=models.PROTECT, null=True, blank=True, related_name="yandex_order")
    status = models.CharField(max_length=64, blank=True)
    substatus = models.CharField(max_length=100, blank=True)
    created_remote_at = models.DateTimeField(null=True, blank=True)
    updated_remote_at = models.DateTimeField(null=True, blank=True)
    payment = json_field(default=dict)
    delivery = json_field(default=dict)
    items = json_field(default=list)
    prices = json_field(default=dict)
    boxes = json_field(default=list)
    fake = models.BooleanField(default=False)
    stock_deducted = models.BooleanField(default=False)
    shipped_once = models.BooleanField(default=False)
    last_error = models.TextField(blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["integration", "order_id"], name="ym_unique_order")]
        ordering = ["-order_id"]


class OrderLine(models.Model):
    order = models.ForeignKey(OrderMetadata, on_delete=models.PROTECT, related_name="lines")
    remote_item_id = models.PositiveBigIntegerField()
    connection = models.ForeignKey(OfferConnection, on_delete=models.PROTECT, related_name="order_lines")
    quantity = models.PositiveIntegerField()
    returned_quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "remote_item_id"], name="ym_unique_order_item"),
            models.CheckConstraint(condition=Q(returned_quantity__lte=models.F("quantity")), name="ym_return_not_above_sold"),
        ]


class ReturnMetadata(models.Model):
    order = models.ForeignKey(OrderMetadata, on_delete=models.PROTECT, related_name="returns")
    return_id = models.PositiveBigIntegerField()
    status = models.CharField(max_length=100, blank=True)
    kind = models.CharField(max_length=100, blank=True)
    snapshot = json_field(default=dict)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.PROTECT, null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "return_id"], name="ym_unique_return")]


class WebhookEvent(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT)
    key = models.CharField(max_length=64)
    event_type = models.CharField(max_length=100)
    order_id = models.PositiveBigIntegerField(null=True)
    return_id = models.PositiveBigIntegerField(null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=20, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["integration", "key"], name="ym_unique_event")]


class SyncJob(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT, related_name="jobs")
    key = models.CharField(max_length=200, unique=True)
    kind = models.CharField(max_length=30)
    payload = json_field(default=dict)
    state = models.CharField(max_length=20, default="pending", db_index=True)
    generation = models.PositiveIntegerField(default=1)
    claimed_generation = models.PositiveIntegerField(default=0)
    lease = models.UUIDField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    run_after = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)


class ApiLog(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    operation = models.CharField(max_length=100)
    direction = models.CharField(max_length=10, default="out")
    entity_id = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10)
    endpoint = models.CharField(max_length=500)
    http_status = models.PositiveIntegerField(null=True)
    result = models.CharField(max_length=20)
    error_code = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)
    request_id = models.CharField(max_length=200, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    attempt = models.PositiveIntegerField(default=0)
    job = models.ForeignKey(SyncJob, on_delete=models.PROTECT, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)

    class Meta:
        ordering = ["-id"]


class ApiBudget(models.Model):
    """Общий счётчик лимита для всех процессов данного кабинета."""
    key = models.CharField(max_length=200, primary_key=True)
    window_start = models.DateTimeField(default=timezone.now)
    used = models.PositiveBigIntegerField(default=0)


class AuditEvent(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=255)
    details = json_field(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class LabelDocument(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.PROTECT)
    order = models.ForeignKey(OrderMetadata, on_delete=models.PROTECT, null=True, blank=True, related_name="labels")
    order_ids = json_field(default=list)
    report_id = models.CharField(max_length=100, blank=True)
    shipment_id = models.PositiveBigIntegerField(null=True, blank=True)
    box_id = models.PositiveBigIntegerField(null=True, blank=True)
    format = models.CharField(max_length=50, default="A7")
    state = models.CharField(max_length=30, default="pending")
    file = models.FileField(upload_to="yandex/labels/%Y/%m/", blank=True)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
