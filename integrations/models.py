from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class IntegrationCredential(models.Model):
    class Provider(models.TextChoices):
        AVITO = "avito", "Avito"

    class Status(models.TextChoices):
        NOT_CONFIGURED = "not_configured", "Не настроено"
        CONNECTED = "connected", "Подключено"
        ERROR = "error", "Ошибка подключения"

    provider = models.CharField("Интеграция", max_length=32, choices=Provider.choices, unique=True)
    encrypted_client_id = models.TextField("Client ID (зашифрован)", blank=True, editable=False)
    encrypted_client_secret = models.TextField("Client secret (зашифрован)", blank=True, editable=False)
    account_id = models.CharField("ID аккаунта", max_length=64, blank=True, editable=False)
    account_name = models.CharField("Название аккаунта", max_length=255, blank=True, editable=False)
    status = models.CharField(
        "Состояние", max_length=24, choices=Status.choices, default=Status.NOT_CONFIGURED, editable=False
    )
    last_checked_at = models.DateTimeField("Последняя проверка", null=True, blank=True, editable=False)
    last_success_at = models.DateTimeField("Последнее успешное подключение", null=True, blank=True, editable=False)
    last_error = models.TextField("Последняя ошибка", blank=True, editable=False)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "параметры интеграции"
        verbose_name_plural = "параметры интеграций"
        permissions = [
            ("view_integrations", "Интеграции: просмотр"),
            ("manage_integration_credentials", "Интеграции: изменение API-ключей"),
            ("view_avito_integration", "Avito: просмотр"),
            ("manage_avito_product", "Avito: изменение профиля товара"),
            ("bind_avito_listing", "Avito: привязка объявления"),
            ("rebind_avito_listing", "Avito: перепривязка объявления"),
            ("manual_avito_sync", "Avito: ручная синхронизация"),
        ]

    @property
    def is_configured(self):
        return bool(self.encrypted_client_id and self.encrypted_client_secret)

    @property
    def masked_client_id(self):
        return "••••••••" if self.encrypted_client_id else ""

    @property
    def masked_client_secret(self):
        return "••••••••" if self.encrypted_client_secret else ""

    def __str__(self):
        return self.get_provider_display()


class AvitoProductProfile(models.Model):
    class SyncStatus(models.TextChoices):
        IDLE = "idle", "Ожидает"
        QUEUED = "queued", "В очереди"
        SYNCING = "syncing", "Синхронизация"
        OK = "ok", "OK"
        ERROR = "error", "Ошибка"

    cd = models.OneToOneField(
        "catalog.CD", on_delete=models.CASCADE, related_name="avito_profile", null=True, blank=True
    )
    tech = models.OneToOneField(
        "catalog.Tech", on_delete=models.CASCADE, related_name="avito_profile", null=True, blank=True
    )
    sell_on_avito = models.BooleanField("Продаётся на Avito", default=False)
    listing_title = models.CharField("Заголовок Avito", max_length=255, blank=True)
    listing_description = models.TextField("Описание Avito", blank=True)
    category_slug = models.CharField("Категория Avito", max_length=255, blank=True)
    category_name = models.CharField("Название категории", max_length=255, blank=True)
    attributes = models.JSONField("Поля Avito", default=dict, blank=True)
    schema_snapshot = models.JSONField("Схема полей Avito", default=dict, blank=True, editable=False)
    sync_status = models.CharField(
        "Состояние синхронизации", max_length=16, choices=SyncStatus.choices, default=SyncStatus.IDLE,
        editable=False,
    )
    last_error = models.TextField("Последняя ошибка", blank=True, editable=False)
    last_successful_sync_at = models.DateTimeField(
        "Последняя успешная синхронизация", null=True, blank=True, editable=False
    )
    desired_state_hash = models.CharField("Хэш состояния", max_length=64, blank=True, editable=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Avito-профиль товара"
        verbose_name_plural = "Avito-профили товаров"
        constraints = [
            models.CheckConstraint(
                condition=(Q(cd__isnull=False, tech__isnull=True) | Q(cd__isnull=True, tech__isnull=False)),
                name="avito_profile_exact_product",
            )
        ]

    @property
    def product(self):
        return self.cd if self.cd_id else self.tech

    @property
    def product_kind(self):
        return "cd" if self.cd_id else "tech"

    @property
    def product_id(self):
        return self.cd_id or self.tech_id

    def clean(self):
        super().clean()
        if bool(self.cd_id) == bool(self.tech_id):
            raise ValidationError("Avito-профиль должен ссылаться ровно на один CD или Tech.")
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Поля Avito должны быть JSON-объектом."})
        if self.schema_snapshot:
            from .schema import validate_attributes
            validate_attributes(self.attributes, self.schema_snapshot)

    def __str__(self):
        return f"Avito — {self.product}"


def avito_photo_upload_to(instance, filename):
    safe_name = f"{instance.pk or 'new'}-{filename}".replace("..", "")
    return f"avito/{instance.profile.product_kind}/{instance.profile.product_id}/{safe_name}"


class AvitoProductPhoto(models.Model):
    class Source(models.TextChoices):
        USER = "user", "Загружено пользователем"
        AVITO = "avito", "Импортировано из Avito"

    profile = models.ForeignKey(
        AvitoProductProfile, on_delete=models.CASCADE, related_name="photos", verbose_name="Avito-профиль"
    )
    image = models.ImageField("Фотография", upload_to=avito_photo_upload_to)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)
    source = models.CharField("Источник", max_length=16, choices=Source.choices, default=Source.USER)
    remote_url = models.URLField("Исходный URL Avito", max_length=1000, blank=True, editable=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Avito-фотография"
        verbose_name_plural = "Avito-фотографии"
        constraints = [
            models.UniqueConstraint(fields=("profile", "sort_order"), name="unique_avito_photo_order")
        ]


class AvitoRemoteListing(models.Model):
    avito_item_id = models.PositiveBigIntegerField("Avito ID", unique=True)
    title = models.CharField("Название", max_length=500, blank=True)
    category_name = models.CharField("Категория", max_length=255, blank=True)
    status = models.CharField("Статус", max_length=64, blank=True)
    remote_price = models.DecimalField(
        "Текущая цена Avito", max_digits=20, decimal_places=2, null=True, blank=True, editable=False
    )
    url = models.URLField("Ссылка", max_length=1000, blank=True)
    snapshot = models.JSONField("Безопасный snapshot", default=dict, blank=True, editable=False)
    last_seen_at = models.DateTimeField("Последний раз получено", null=True, blank=True, editable=False)
    missing_since = models.DateTimeField("Не найдено с", null=True, blank=True, editable=False)

    class Meta:
        ordering = ("-last_seen_at", "-avito_item_id")
        verbose_name = "объявление Avito"
        verbose_name_plural = "объявления Avito"

    def __str__(self):
        return f"Avito #{self.avito_item_id}: {self.title}"


class AvitoListingConnection(models.Model):
    profile = models.OneToOneField(
        AvitoProductProfile, on_delete=models.CASCADE, related_name="connection", verbose_name="Профиль товара"
    )
    remote_listing = models.OneToOneField(
        AvitoRemoteListing, on_delete=models.PROTECT, related_name="connection", verbose_name="Объявление Avito"
    )
    created_at = models.DateTimeField("Привязано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "привязка объявления Avito"
        verbose_name_plural = "привязки объявлений Avito"

    def __str__(self):
        return f"{self.profile} ↔ #{self.remote_listing.avito_item_id}"


class AvitoSyncJob(models.Model):
    class JobType(models.TextChoices):
        PRODUCT = "product", "Товар"
        RECONCILE = "reconcile", "Контрольная сверка"
        REFRESH = "refresh", "Обновление объявлений"
        MANUAL = "manual", "Ручная сверка"
        STATUS_REFRESH = "status_refresh", "Обновление статусов объявлений"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        RUNNING = "running", "Выполняется"
        DONE = "done", "Выполнено"
        ERROR = "error", "Ошибка"

    dedupe_key = models.CharField("Ключ объединения", max_length=100, unique=True)
    job_type = models.CharField("Тип", max_length=16, choices=JobType.choices)
    profile = models.ForeignKey(
        AvitoProductProfile, on_delete=models.CASCADE, related_name="sync_jobs", null=True, blank=True
    )
    status = models.CharField("Статус", max_length=16, choices=Status.choices, default=Status.PENDING)
    run_after = models.DateTimeField("Выполнить после")
    attempts = models.PositiveSmallIntegerField("Попытки", default=0)
    last_error = models.TextField("Последняя ошибка", blank=True)
    total_count = models.PositiveIntegerField("Объявлений к проверке", default=0)
    checked_count = models.PositiveIntegerField("Проверено", default=0)
    changed_count = models.PositiveIntegerField("Изменено и подтверждено", default=0)
    stock_changed_count = models.PositiveIntegerField("Исправлено остатков", default=0)
    price_changed_count = models.PositiveIntegerField("Исправлено цен", default=0)
    failed_count = models.PositiveIntegerField("Не удалось синхронизировать", default=0)
    skipped_count = models.PositiveIntegerField("Неактивных или вне списка", default=0)
    details = models.JSONField("Итог сверки", default=list, blank=True)
    phase = models.CharField("Этап сверки", max_length=120, blank=True)
    current_item = models.CharField("Текущий товар", max_length=255, blank=True)
    started_at = models.DateTimeField("Начало сверки", null=True, blank=True)
    finished_at = models.DateTimeField("Завершение сверки", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        ordering = ("run_after", "id")
        indexes = [models.Index(fields=("status", "run_after"), name="avito_job_due_idx")]
        verbose_name = "задача синхронизации Avito"
        verbose_name_plural = "задачи синхронизации Avito"


class AvitoSyncLog(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "Успешно"
        ERROR = "error", "Ошибка"
        SKIPPED = "skipped", "Пропущено"

    profile = models.ForeignKey(
        AvitoProductProfile, on_delete=models.SET_NULL, related_name="sync_logs", null=True, blank=True
    )
    remote_listing = models.ForeignKey(
        AvitoRemoteListing, on_delete=models.SET_NULL, related_name="sync_logs", null=True, blank=True
    )
    operation = models.CharField("Операция", max_length=64)
    result = models.CharField("Результат", max_length=16, choices=Result.choices)
    http_status = models.PositiveSmallIntegerField("HTTP-статус", null=True, blank=True)
    error_category = models.CharField("Категория ошибки", max_length=32, blank=True)
    message = models.TextField("Сообщение", blank=True)
    retry_number = models.PositiveSmallIntegerField("Номер попытки", default=0)
    started_at = models.DateTimeField("Начало")
    finished_at = models.DateTimeField("Завершение", auto_now_add=True)

    class Meta:
        ordering = ("-started_at", "-id")
        verbose_name = "запись синхронизации Avito"
        verbose_name_plural = "журнал синхронизации Avito"


class IntegrationAuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="integration_events"
    )
    action = models.CharField("Действие", max_length=64)
    product_kind = models.CharField("Тип товара", max_length=8, blank=True)
    product_id = models.PositiveBigIntegerField("ID товара", null=True, blank=True)
    details = models.JSONField("Детали без секретов", default=dict, blank=True)
    created_at = models.DateTimeField("Дата и время", auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "событие интеграции"
        verbose_name_plural = "аудит интеграций"
