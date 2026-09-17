import re
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class NamedReference(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self):
        return self.name


class Platform(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "платформа"
        verbose_name_plural = "платформы"


class Brand(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "бренд"
        verbose_name_plural = "бренды"


class ProductType(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "тип товара"
        verbose_name_plural = "типы товара"


def normalize_game_series_name(value):
    name = unicodedata.normalize("NFKC", str(value or ""))
    name = name.translate(str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"}))
    return re.sub(r"\s+", " ", name).strip()


class GameSeries(models.Model):
    name = models.CharField("Название", max_length=255)
    normalized_name = models.CharField("Нормализованное название", max_length=255, unique=True, editable=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "игровая серия"
        verbose_name_plural = "игровые серии"

    def clean(self):
        super().clean()
        self.name = normalize_game_series_name(self.name)
        if not self.name:
            raise ValidationError({"name": "Укажите название игровой серии."})
        self.normalized_name = self.name.casefold()
        if GameSeries.objects.filter(normalized_name=self.normalized_name).exclude(pk=self.pk).exists():
            raise ValidationError({"name": "Игровая серия с таким названием уже существует."})

    def save(self, *args, **kwargs):
        self.clean()
        if kwargs.get("update_fields") is not None and "name" in kwargs["update_fields"]:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"normalized_name", "updated_at"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)


class ProductBase(models.Model):
    objects = ProductQuerySet.as_manager()
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    sku = models.CharField("Артикул", max_length=100, blank=True)
    barcode = models.CharField("Штрихкод", max_length=100, blank=True)
    quantity_on_consignment = models.PositiveIntegerField("На реализации", default=0, editable=False)
    cost = models.DecimalField(
        "Средняя себестоимость", max_digits=20, decimal_places=2,
        default=0, validators=[MinValueValidator(0)],
    )
    avito_price = models.DecimalField(
        "Цена Avito", max_digits=20, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    wholesale_price = models.DecimalField(
        "Оптовая цена", max_digits=20, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    yandex_market_price = models.DecimalField(
        "Цена Яндекс Маркет", max_digits=20, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    comment = models.TextField("Комментарий", blank=True)
    is_archived = models.BooleanField("Удалён из активной номенклатуры", default=False, db_index=True)
    archived_at = models.DateTimeField("Дата удаления", null=True, blank=True, editable=False)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False, verbose_name="Кем удалён",
    )

    class Meta:
        abstract = True
        ordering = ("name", "id")

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.sku = str(self.sku or "").strip()
        self.barcode = str(self.barcode or "").strip()
        if not self.barcode:
            return
        for model in (CD, Tech):
            queryset = model.objects.filter(barcode=self.barcode)
            if isinstance(self, model) and self.pk:
                queryset = queryset.exclude(pk=self.pk)
            if queryset.exists():
                raise ValidationError({
                    "barcode": "Этот штрихкод уже используется другим товаром."
                })


class CD(ProductBase):
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="cds", verbose_name="Платформа")
    game_series = models.ForeignKey(
        GameSeries, on_delete=models.PROTECT, related_name="cds",
        verbose_name="Игровая серия", null=True, blank=True,
    )
    cusa_ppsa_code = models.CharField("CUSA/PPSA код", max_length=100, blank=True)
    weight_grams = models.PositiveIntegerField(
        "Вес, г", default=120, blank=True, validators=[MinValueValidator(1)]
    )

    def clean(self):
        if self.weight_grams is None:
            self.weight_grams = 120
        super().clean()

    class Meta(ProductBase.Meta):
        verbose_name = "CD"
        verbose_name_plural = "CD"
        permissions = [
            ("view_nomenclature", "Номенклатура: просмотр"),
            ("change_cd_platform", "CD: изменение платформы"),
            ("change_cd_game_series", "CD: изменение игровой серии"),
            ("change_cd_name", "CD: изменение названия"),
            ("change_cd_description", "CD: изменение описания"),
            ("change_cd_sku", "CD: изменение артикула"),
            ("change_cd_barcode", "CD: изменение штрихкода"),
            ("change_cd_weight", "CD: изменение веса"),
            ("change_cd_cusa_ppsa_code", "CD: изменение CUSA/PPSA"),
            ("change_cd_comment", "CD: изменение комментария"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_on_consignment__gte=0), name="cd_consignment_nonnegative"),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="cd_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(avito_price__gte=0) | models.Q(avito_price__isnull=True), name="cd_avito_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(wholesale_price__gte=0) | models.Q(wholesale_price__isnull=True), name="cd_wholesale_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(yandex_market_price__gte=0) | models.Q(yandex_market_price__isnull=True), name="cd_yandex_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(weight_grams__gt=0), name="cd_weight_positive"),
        ]


class Tech(ProductBase):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Бренд")
    product_type = models.ForeignKey(ProductType, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Тип товара")
    weight_grams = models.PositiveIntegerField(
        "Вес, г", null=True, blank=True, validators=[MinValueValidator(1)]
    )

    class Meta(ProductBase.Meta):
        verbose_name = "техника"
        verbose_name_plural = "техника"
        permissions = [
            ("change_tech_brand", "Tech: изменение бренда"),
            ("change_tech_product_type", "Tech: изменение типа товара"),
            ("change_tech_name", "Tech: изменение названия"),
            ("change_tech_description", "Tech: изменение описания"),
            ("change_tech_sku", "Tech: изменение артикула"),
            ("change_tech_barcode", "Tech: изменение штрихкода"),
            ("change_tech_weight", "Tech: изменение веса"),
            ("change_tech_comment", "Tech: изменение комментария"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_on_consignment__gte=0), name="tech_consignment_nonnegative"),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="tech_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(avito_price__gte=0) | models.Q(avito_price__isnull=True), name="tech_avito_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(wholesale_price__gte=0) | models.Q(wholesale_price__isnull=True), name="tech_wholesale_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(yandex_market_price__gte=0) | models.Q(yandex_market_price__isnull=True), name="tech_yandex_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(weight_grams__gt=0) | models.Q(weight_grams__isnull=True),
                name="tech_weight_positive_or_null",
            ),
        ]


class ProductRemovalEvent(models.Model):
    class Action(models.TextChoices):
        HARD_DELETE = "hard_delete", "Безвозвратное удаление"
        ARCHIVE = "archive", "Удаление с сохранением истории"

    action = models.CharField("Действие", max_length=16, choices=Action.choices)
    product_kind = models.CharField("Тип товара", max_length=8)
    product_id = models.PositiveBigIntegerField("ID товара")
    product_sku = models.CharField("Артикул", max_length=100, blank=True)
    product_name = models.CharField("Название", max_length=255)
    reason = models.TextField("Причина")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="product_removal_events", verbose_name="Пользователь",
    )
    created_at = models.DateTimeField("Дата и время", auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "удаление товара"
        verbose_name_plural = "удаления товаров"


class BarcodeRegistry(models.Model):
    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    value = models.CharField("Штрихкод", max_length=100, unique=True)
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices)
    cd = models.OneToOneField(
        CD, on_delete=models.CASCADE, related_name="barcode_registration",
        null=True, blank=True, verbose_name="CD",
    )
    tech = models.OneToOneField(
        Tech, on_delete=models.CASCADE, related_name="barcode_registration",
        null=True, blank=True, verbose_name="Tech",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ("value",)
        verbose_name = "регистрация штрихкода"
        verbose_name_plural = "реестр штрихкодов"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="barcode_registry_exact_product",
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    def clean(self):
        super().clean()
        self.value = str(self.value or "").strip()
        valid = (
            self.product_kind == self.ProductKind.CD and self.cd_id and not self.tech_id
        ) or (
            self.product_kind == self.ProductKind.TECH and self.tech_id and not self.cd_id
        )
        if not valid:
            raise ValidationError("Регистрация штрихкода должна ссылаться ровно на один товар.")

    def __str__(self):
        return self.value


class ProductChangeEvent(models.Model):
    class Source(models.TextChoices):
        NOMENCLATURE = "nomenclature", "Номенклатура"
        CRM = "crm", "CRM"
        DJANGO_ADMIN = "django_admin", "Django Admin"

    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    class ActionKind(models.TextChoices):
        SALE = "sale", "Продажа"
        WAREHOUSE_TRANSFER = "warehouse_transfer", "Перемещение"
        CONSIGNMENT = "consignment", "Реализация"
        SUPPLY = "supply", "Поставка"
        SUPPLY_FINALIZATION = "supply_finalization", "Финализация прихода"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_change_events",
        verbose_name="Пользователь",
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField("Дата и время", auto_now_add=True, editable=False)
    source = models.CharField("Источник", max_length=24, choices=Source.choices, editable=False)
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices, editable=False)
    cd = models.ForeignKey(
        CD,
        on_delete=models.PROTECT,
        related_name="change_events",
        verbose_name="CD",
        null=True,
        blank=True,
        editable=False,
    )
    tech = models.ForeignKey(
        Tech,
        on_delete=models.PROTECT,
        related_name="change_events",
        verbose_name="Tech",
        null=True,
        blank=True,
        editable=False,
    )
    action_kind = models.CharField(
        "Тип связанного действия",
        max_length=32,
        choices=ActionKind.choices,
        blank=True,
        editable=False,
    )
    action_object_id = models.PositiveBigIntegerField(
        "ID связанного действия", null=True, blank=True, editable=False
    )
    action_label = models.CharField(
        "Номер связанного действия", max_length=120, blank=True, editable=False
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "событие изменения товара"
        verbose_name_plural = "история изменений товаров"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="product_change_event_exact_product",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(action_kind="", action_object_id__isnull=True, action_label="")
                    | (
                        ~models.Q(action_kind="")
                        & models.Q(action_object_id__isnull=False)
                        & ~models.Q(action_label="")
                    )
                ),
                name="product_change_event_valid_action",
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    def __str__(self):
        created = self.created_at.strftime("%d.%m.%Y %H:%M") if self.created_at else "новое событие"
        return f"{self.get_product_kind_display()} #{self.product_id} — {created}"

    @property
    def product_id(self):
        return self.cd_id if self.product_kind == self.ProductKind.CD else self.tech_id

    @property
    def executor_display(self):
        if self.actor_id:
            actor_name = self.actor.full_name or self.actor.username
            if self.source == self.Source.NOMENCLATURE:
                return actor_name
            return f"{actor_name} ({self.get_source_display()})"
        return self.get_source_display()

    @property
    def action_url(self):
        if not self.action_kind or self.action_object_id is None:
            return ""
        route = {
            self.ActionKind.SALE: "sales:detail",
            self.ActionKind.WAREHOUSE_TRANSFER: "warehouse:transfer_detail",
            self.ActionKind.CONSIGNMENT: "consignment:movement_detail",
            self.ActionKind.SUPPLY: "supplies:detail",
            self.ActionKind.SUPPLY_FINALIZATION: "supplies:detail",
        }.get(self.action_kind)
        return reverse(route, args=(self.action_object_id,)) if route else ""


class ProductFieldChange(models.Model):
    event = models.ForeignKey(
        ProductChangeEvent,
        on_delete=models.CASCADE,
        related_name="field_changes",
        verbose_name="Событие",
        editable=False,
    )
    field_name = models.CharField("Поле", max_length=100, editable=False)
    field_label = models.CharField("Название поля", max_length=255, editable=False)
    old_value = models.TextField("Старое значение", blank=True, editable=False)
    new_value = models.TextField("Новое значение", blank=True, editable=False)

    class Meta:
        ordering = ("id",)
        verbose_name = "изменение поля товара"
        verbose_name_plural = "изменения полей товаров"

    def __str__(self):
        return f"{self.field_label}: {self.old_value or '—'} → {self.new_value or '—'}"
