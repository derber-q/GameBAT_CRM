"""Цифровые предложения отделены от CD/Tech, продаж, складов и денежных журналов."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class Integration(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False)
    encrypted_key = models.TextField(blank=True)
    daily_enabled = models.BooleanField(default=False)
    daily_at = models.TimeField(null=True, blank=True)
    timezone_name = models.CharField(max_length=64, default='Europe/Moscow')
    revision = models.PositiveIntegerField(default=1)
    last_success_at = models.DateTimeField(null=True, blank=True)
    next_at = models.DateTimeField(null=True, blank=True)
    error_category = models.CharField(max_length=40, blank=True)
    manual_sheet_enabled = models.BooleanField(default=False)
    manual_sheet_url = models.URLField(max_length=500, blank=True)
    manual_sheet_last_success_at = models.DateTimeField(null=True, blank=True)
    manual_sheet_error_category = models.CharField(max_length=40, blank=True)


class CatalogState(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    revision = models.PositiveBigIntegerField(default=0)
    source_at = models.DateTimeField(null=True, blank=True)


class ProviderGate(models.Model):
    """Общее окно запросов всех процессов; ключ и ответы здесь не хранятся."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    revision = models.PositiveBigIntegerField(default=0)
    requests_at = models.JSONField(default=list)
    blocked_until = models.DateTimeField(null=True)
    urgent_until = models.DateTimeField(null=True)


class Product(models.Model):
    class Rule(models.TextChoices):
        PS_PLUS = 'ps_plus_subscription', 'PlayStation Plus · вверх до 50 ₽'
        XBOX = 'xbox_subscription', 'Подписка Xbox · вверх до 50 ₽'
        OTHER = 'other', 'Остальное · вверх до 10 ₽'

    class Availability(models.TextChoices):
        YES = 'yes', 'Доступен'
        NO = 'no', 'Нет в наличии'
        UNKNOWN = 'unknown', 'Наличие уточняется'

    external_id = models.CharField(max_length=128, unique=True)
    legacy_external_id = models.CharField(max_length=128, blank=True)
    api_version = models.PositiveSmallIntegerField(default=0)
    fulfillment = models.CharField(max_length=12, blank=True)
    requirements = models.JSONField(default=dict, blank=True)
    quantity_limits = models.JSONField(default=dict, blank=True)
    mapping_issue = models.CharField(max_length=40, blank=True)
    superseded_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='legacy_cards')
    source_name = models.CharField(max_length=500)
    source_type = models.CharField(max_length=40)
    platform = models.CharField(max_length=60, blank=True)
    region = models.CharField(max_length=80, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    purchase_cost = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8)
    markup = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    rule = models.CharField(max_length=24, choices=Rule.choices, default=Rule.OTHER)
    rule_manual = models.BooleanField(default=False)
    display_name = models.CharField(max_length=500, blank=True)
    category = models.CharField(max_length=120, blank=True)
    category_manual = models.BooleanField(default=False)
    section = models.CharField(max_length=12, choices=[('services', 'Подписки и услуги'), ('codes', 'Цифровые коды')], default='services')
    position = models.IntegerField(default=0)
    availability = models.CharField(max_length=10, choices=Availability.choices, default=Availability.UNKNOWN)
    requires_review = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    confirmed_at = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['section', 'position', 'category', 'display_name', 'source_name', 'pk']
        constraints = [models.CheckConstraint(condition=Q(markup__isnull=True) | Q(markup__gte=0), name='digital_price_markup_positive'),
                       models.CheckConstraint(condition=Q(purchase_cost__isnull=True) | Q(purchase_cost__gte=0), name='digital_price_cost_positive')]
        permissions = [('view_catalog', 'Просмотр цифрового каталога'), ('view_cost', 'Просмотр себестоимости и наценок'),
            ('edit_markup', 'Изменение фиксированных наценок'), ('edit_cost', 'Изменение ручной себестоимости цифровых товаров'),
            ('sync_catalog', 'Обновление цифрового каталога'),
            ('download_prices', 'Скачивание клиентских PNG-прайсов'), ('edit_layout', 'Категории, оформление и округление'),
            ('configure_integration', 'Настройка интеграции цифрового каталога')]


class SyncJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=12, default='pending')
    source = models.CharField(max_length=12, default='manual')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    attempts = models.PositiveSmallIntegerField(default=0)
    run_after = models.DateTimeField()
    owner = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    error_category = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    item_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['active'], condition=Q(active=True), name='digital_one_active_catalog_sync')]


class ManualPriceEntry(models.Model):
    """Ручная закупка и наценка: суммы RUB и проценты хранятся раздельно."""
    class Kind(models.TextChoices):
        GAME = 'game_tariff', 'Игры по странам'
        STEAM = 'steam_tariff', 'Пополнение Steam'

    class Unit(models.TextChoices):
        RUB = 'rub', 'Рубли'
        PERCENT = 'percent', 'Проценты'
        COEFFICIENT = 'coefficient', 'Коэффициент'

    class PricingMode(models.TextChoices):
        RUB = 'rub', '₽'
        PERCENT = 'percent', '%'
        COEFFICIENT = 'coefficient', 'Коэффициент'

    kind = models.CharField(max_length=16, choices=Kind.choices)
    source_archived = models.BooleanField('Прежний диапазон поставщика', default=False, db_default=False)
    region = models.CharField(max_length=40, blank=True)
    label = models.CharField(max_length=180)
    # Прежние клиентские значения оставлены для истории; новый расчёт их не читает.
    value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    manual_cost = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    markup = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    pricing_mode = models.CharField(max_length=12, choices=PricingMode.choices, default=PricingMode.RUB)
    cost_percent = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    markup_percent = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    cost_coefficient = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    markup_coefficient = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    sheet_reference = models.CharField(max_length=160, blank=True)
    sheet_checked_at = models.DateTimeField(null=True, blank=True)
    sheet_issue = models.CharField(max_length=40, blank=True)
    unit = models.CharField(max_length=12, choices=Unit.choices, default=Unit.RUB)
    position = models.IntegerField(default=0)
    revision = models.PositiveIntegerField(default=1)
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['kind', 'region', 'position', 'pk']
        constraints = [models.CheckConstraint(condition=Q(value__isnull=True) | Q(value__gte=0), name='digital_manual_value_nonnegative'),
                       models.CheckConstraint(condition=Q(manual_cost__isnull=True) | Q(manual_cost__gte=0), name='digital_tariff_cost_positive'),
                       models.CheckConstraint(condition=Q(markup__isnull=True) | Q(markup__gte=0), name='digital_tariff_markup_positive'),
                       models.CheckConstraint(condition=Q(cost_percent__isnull=True) | Q(cost_percent__gte=0), name='digital_tariff_percent_cost_positive'),
                       models.CheckConstraint(condition=Q(markup_percent__isnull=True) | Q(markup_percent__gte=0), name='digital_tariff_percent_markup_positive'),
                       models.CheckConstraint(condition=Q(cost_coefficient__isnull=True) | Q(cost_coefficient__gte=0), name='digital_tariff_coef_cost_positive'),
                       models.CheckConstraint(condition=Q(markup_coefficient__isnull=True) | Q(markup_coefficient__gte=0), name='digital_tariff_coef_markup_positive')]
        permissions = [('edit_manual_prices', 'Изменение ручных клиентских тарифов')]


class BuyerMarkup(models.Model):
    """Отдельная наценка покупателя; себестоимость всегда берётся из каталога."""
    buyer = models.ForeignKey('digital_sales.Buyer', on_delete=models.PROTECT, related_name='price_markups')
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT)
    manual_entry = models.ForeignKey(ManualPriceEntry, null=True, blank=True, on_delete=models.PROTECT)
    markup = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    markup_percent = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    markup_coefficient = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    edited_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(product__isnull=False, manual_entry__isnull=True) |
                Q(product__isnull=True, manual_entry__isnull=False)), name='digital_buyer_markup_one_target'),
            models.UniqueConstraint(fields=['buyer', 'product'], name='digital_buyer_product_once'),
            models.UniqueConstraint(fields=['buyer', 'manual_entry'], name='digital_buyer_manual_once'),
            models.CheckConstraint(condition=Q(markup__isnull=True) | Q(markup__gte=0), name='digital_buyer_markup_positive'),
            models.CheckConstraint(condition=Q(markup_percent__isnull=True) | Q(markup_percent__gte=0), name='digital_buyer_percent_positive'),
            models.CheckConstraint(condition=Q(markup_coefficient__isnull=True) | Q(markup_coefficient__gte=0), name='digital_buyer_coef_positive'),
        ]


class AuditEvent(models.Model):
    product = models.ForeignKey(Product, null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    kind = models.CharField(max_length=32)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class PriceBundle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    buyer = models.ForeignKey('digital_sales.Buyer', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    buyer_name_snapshot = models.CharField(max_length=160, blank=True, default='')
    revision = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    source_at = models.DateTimeField(null=True)
    public_snapshot = models.JSONField(default=dict)


class PricePage(models.Model):
    bundle = models.ForeignKey(PriceBundle, on_delete=models.CASCADE, related_name='pages')
    index = models.PositiveIntegerField()
    filename = models.CharField(max_length=100)
    png = models.BinaryField()
    row_count = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    class Meta:
        ordering = ['index']
        constraints = [models.UniqueConstraint(fields=['bundle', 'index'], name='digital_bundle_page_once')]


class BotBundle(models.Model):
    job = models.OneToOneField('telegram_bots.StaffBotJob', primary_key=True, on_delete=models.CASCADE)
    bundle = models.ForeignKey(PriceBundle, on_delete=models.PROTECT)


class BuyerPriceRequest(models.Model):
    """Выбранный в боте покупатель фиксируется до запуска формирования документов."""
    job = models.OneToOneField('telegram_bots.StaffBotJob', on_delete=models.CASCADE, primary_key=True)
    buyer = models.ForeignKey('digital_sales.Buyer', on_delete=models.PROTECT)


class PageDelivery(models.Model):
    job = models.ForeignKey('telegram_bots.StaffBotJob', on_delete=models.CASCADE)
    page = models.ForeignKey(PricePage, on_delete=models.PROTECT)
    state = models.CharField(max_length=12, default='pending')
    message_id = models.BigIntegerField(null=True)
    error_category = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['job', 'page'], name='digital_page_delivery_once')]


class BuyerPriceDispatch(models.Model):
    """Один комплект покупателю на успешное обновление; сеть выполняется отдельно."""
    sync_job = models.ForeignKey(SyncJob, on_delete=models.PROTECT)
    buyer = models.ForeignKey('digital_sales.Buyer', on_delete=models.PROTECT)
    chat = models.ForeignKey('digital_sales.BuyerBalanceChat', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    bundle = models.ForeignKey(PriceBundle, null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=12, default='queued')
    owner = models.UUIDField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True)
    error_category = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sync_job', 'buyer'], name='digital_buyer_price_dispatch_once')]


class BuyerPriceDispatchPage(models.Model):
    """Доставка страницы и её закреп: done → pinned → unpinned, без повтора фото."""
    dispatch = models.ForeignKey(BuyerPriceDispatch, on_delete=models.PROTECT, related_name='deliveries')
    page = models.ForeignKey(PricePage, on_delete=models.PROTECT)
    caption = models.CharField(max_length=1024)
    state = models.CharField(max_length=12, default='pending')
    message_id = models.BigIntegerField(null=True)
    error_category = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dispatch', 'page'], name='digital_buyer_dispatch_page_once')]
