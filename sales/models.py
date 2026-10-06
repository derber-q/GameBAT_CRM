import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import SalesPlatform
from warehouse.models import Warehouse


def temporary_sale_id():
    return f"TMP-{uuid.uuid4().hex}"


class Sale(models.Model):
    class PriceType(models.TextChoices):
        RETAIL = "retail", "Цена Avito"
        WHOLESALE = "wholesale", "Оптовая"
        YANDEX_MARKET = "yandex_market", "Яндекс Маркет"
        CONSIGNMENT = "consignment", "Реализация"

    class SaleType(models.TextChoices):
        RETAIL = "retail", "Розница"
        WHOLESALE = "wholesale", "Опт"
        AVITO = "avito", "Авито"
        YANDEX_MARKET = "yandex_market", "Яндексмаркет"
        CONSIGNMENT = "consignment", "Реализация"

    class PaymentMethod(models.TextChoices):
        UNDEFINED = "undefined", "Не определён"
        CASH = "cash", "Наличные"
        CASH_POSTPAY = "cash_postpay", "Наличные — постоплата"
        BANK_ACCOUNT = "bank_account", "Банковский счёт"

    class OrderStatus(models.TextChoices):
        CREATED = "created", "Создан"
        ASSEMBLED = "assembled", "Собран"
        SHIPPED = "shipped", "Отправлен"
        DELIVERED = "delivered", "Доставлен"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачен"
        PAID = "paid", "Оплачен"

    visible_id = models.CharField(
        "Номер продажи", max_length=40, unique=True, default=temporary_sale_id, editable=False
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sales", verbose_name="Склад")
    consignment_platform = models.ForeignKey(
        SalesPlatform, on_delete=models.PROTECT, related_name="sales",
        verbose_name="Площадка реализации", null=True, blank=True, editable=False,
    )
    price_type = models.CharField("Тип цены", max_length=24, choices=PriceType.choices)
    sale_type = models.CharField("Тип продажи", max_length=24, choices=SaleType.choices)
    payment_method = models.CharField("Способ оплаты", max_length=24, choices=PaymentMethod.choices)
    order_status = models.CharField(
        "Статус заказа", max_length=20, choices=OrderStatus.choices, default=OrderStatus.CREATED, editable=False
    )
    payment_status = models.CharField(
        "Статус оплаты", max_length=20, choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID, editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_sales", verbose_name="Создал",
        null=True, blank=True,
    )
    storefront_source = models.CharField("Источник", max_length=32, blank=True, default="")
    wholesale_contact = models.ForeignKey(
        "resource_storefront.WholesaleContact", null=True, blank=True, on_delete=models.PROTECT,
        related_name="sales", verbose_name="Оптовый контакт",
    )
    buyer_name_snapshot = models.CharField("Контактное имя на момент заказа", max_length=160, blank=True)
    buyer_phone_snapshot = models.CharField("Основной телефон на момент заказа", max_length=40, blank=True)
    buyer_address_snapshot = models.TextField("Адрес на момент заказа", blank=True)
    buyer_extra_phone = models.CharField("Дополнительный телефон покупателя", max_length=40, blank=True)
    buyer_comment = models.TextField("Комментарий покупателя", blank=True)
    buyer_contact_methods = models.JSONField("Способы связи покупателя", default=list, blank=True)
    buyer_telegram = models.CharField("Telegram покупателя", max_length=80, blank=True)
    buyer_whatsapp = models.CharField("WhatsApp покупателя", max_length=40, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    completed_at = models.DateTimeField("Завершена", null=True, blank=True, editable=False)
    total_amount = models.DecimalField("Сумма", max_digits=20, decimal_places=2, default=0, editable=False)
    cash_received_amount = models.DecimalField(
        "Получено от покупателя", max_digits=20, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)], editable=False,
    )
    extra_cash_amount = models.DecimalField(
        "Сумма сверх стоимости", max_digits=20, decimal_places=2, default=0,
        validators=[MinValueValidator(0)], editable=False,
    )
    note = models.TextField("Примечание", blank=True)
    cancelled_at = models.DateTimeField("Отменена", null=True, blank=True, editable=False)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cancelled_sales",
        verbose_name="Отменил", null=True, blank=True, editable=False,
    )
    cancellation_comment = models.TextField("Причина отмены", blank=True, editable=False)
    refunded_amount = models.DecimalField(
        "Возвращённая сумма", max_digits=20, decimal_places=2, default=0,
        validators=[MinValueValidator(0)], editable=False,
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "продажа"
        verbose_name_plural = "продажи"
        permissions = [
            ("view_sales", "Может просматривать незавершённые продажи"),
            ("view_completed_sales", "Может просматривать завершённые продажи"),
            ("view_sale_detail", "Может просматривать подробности продажи"),
            ("create_sale", "Может создавать продажи"),
            ("edit_unpaid_postpay_sale", "Может изменять неоплаченную продажу с постоплатой"),
            ("advance_order_status", "Может менять статус заказа"),
            ("mark_sale_paid", "Может подтверждать оплату продажи"),
            ("import_wholesale_price", "Может импортировать оптовый XLSX в новую продажу"),
            ("cancel_sale", "Может отменять продажи"),
            ("view_sales_statistics", "Может просматривать статистику продаж и прибыль"),
            ("export_sales_statistics", "Может экспортировать статистику продаж"),
        ]
        constraints = [
            models.CheckConstraint(condition=~models.Q(payment_method="undefined") | models.Q(payment_status="unpaid"), name="sale_undefined_payment_unpaid"),
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="sale_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(refunded_amount__gte=0), name="sale_refund_nonnegative"),
            models.CheckConstraint(
                condition=(
                    models.Q(cash_received_amount__isnull=True, refunded_amount__lte=models.F("total_amount"))
                    | models.Q(
                        cash_received_amount__isnull=False,
                        refunded_amount__lte=models.F("cash_received_amount"),
                    )
                ),
                name="sale_refund_not_above_received",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(cash_received_amount__isnull=True)
                    | models.Q(cash_received_amount__gte=models.F("total_amount"))
                ),
                name="sale_cash_received_not_below_total",
            ),
            models.CheckConstraint(
                condition=models.Q(extra_cash_amount__gte=0),
                name="sale_extra_cash_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(payment_method__in=("cash", "cash_postpay"))
                    | models.Q(cash_received_amount__isnull=True, extra_cash_amount=0)
                ),
                name="sale_bank_has_no_cash_received",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        cancelled_at__isnull=True, cancelled_by__isnull=True,
                        cancellation_comment="", refunded_amount=0,
                    )
                    | (
                        models.Q(cancelled_at__isnull=False, cancelled_by__isnull=False)
                        & ~models.Q(cancellation_comment="")
                    )
                ),
                name="sale_cancellation_fields_consistent",
            ),
        ]

    @property
    def is_completed(self):
        return (
            not self.is_cancelled
            and self.order_status == self.OrderStatus.DELIVERED
            and self.payment_status == self.PaymentStatus.PAID
        )

    @property
    def storefront_source_label(self):
        return {"resource_storefront": "Оптовый сайт", "resource_retail": "Розничный сайт"}.get(self.storefront_source, self.storefront_source)

    @property
    def buyer_contact_methods_label(self):
        labels = {"telegram": "Telegram", "whatsapp": "WhatsApp", "phone": "Звонок по телефону"}
        return ", ".join(labels.get(method, method) for method in self.buyer_contact_methods)

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    @property
    def is_postpay_editable(self):
        return (
            not self.is_cancelled
            and self.payment_method == self.PaymentMethod.CASH_POSTPAY
            and self.payment_status == self.PaymentStatus.UNPAID
            and self.order_status != self.OrderStatus.DELIVERED
        )

    @property
    def position_count(self):
        if self.sale_type == self.SaleType.CONSIGNMENT and self._related_items("consignment_items"):
            return len(self._related_items("consignment_items"))
        return sum(len(self._related_items(name)) for name in (
            "cd_items", "tech_items", "custom_items", "consignment_items",
        ))

    @property
    def total_units(self):
        if self.sale_type == self.SaleType.CONSIGNMENT and self._related_items("consignment_items"):
            return sum(item.quantity for item in self._related_items("consignment_items"))
        return sum(item.quantity for name in (
            "cd_items", "tech_items", "custom_items", "consignment_items",
        ) for item in self._related_items(name))

    def _related_items(self, name):
        cached = getattr(self, "_prefetched_objects_cache", {}).get(name)
        return cached if cached is not None else getattr(self, name).all()

    def __str__(self):
        return self.visible_id

    def save(self, *args, **kwargs):
        """Разрешает только одно служебное преобразование TMP-id в постоянный номер продажи."""
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).values("visible_id", "completed_at").first()
            stored_id = stored["visible_id"] if stored else None
            if stored_id and not stored_id.startswith("TMP-") and stored_id != self.visible_id:
                raise ValidationError("Номер созданной продажи изменять нельзя.")
            if stored and stored["completed_at"] is not None and stored["completed_at"] != self.completed_at:
                raise ValidationError("Дату завершения продажи изменять нельзя.")
        return super().save(*args, **kwargs)


class SaleItemBase(models.Model):
    quantity = models.PositiveIntegerField("Количество")
    unit_price = models.DecimalField("Цена единицы", max_digits=20, decimal_places=2)
    unit_discount = models.DecimalField(
        "Скидка на единицу", max_digits=20, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    line_total = models.DecimalField("Сумма строки", max_digits=20, decimal_places=2)
    avito_commission_enabled = models.BooleanField(
        "Учитывать комиссию Avito 0,5%", default=False, editable=False,
    )
    avito_commission_amount = models.DecimalField(
        "Комиссия Avito", max_digits=20, decimal_places=2, default=0,
        validators=[MinValueValidator(0)], editable=False,
    )
    unit_cost_snapshot = models.DecimalField(
        "Себестоимость единицы на момент продажи", max_digits=20, decimal_places=2,
        null=True, blank=True, editable=False,
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255)
    article_snapshot = models.CharField("Артикул", max_length=100)

    class Meta:
        abstract = True

    @property
    def effective_unit_price(self):
        return self.unit_price - self.unit_discount

    @property
    def revenue_after_avito_commission(self):
        return self.line_total - self.avito_commission_amount

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).values(
                "unit_cost_snapshot", "avito_commission_enabled", "avito_commission_amount",
                "sale__completed_at",
            ).first()
            if stored and stored["unit_cost_snapshot"] != self.unit_cost_snapshot:
                raise ValidationError("Историческую себестоимость продажи изменять нельзя.")
            commission_changed = stored and (
                stored["avito_commission_enabled"] != self.avito_commission_enabled
                or stored["avito_commission_amount"] != self.avito_commission_amount
            )
            if commission_changed and stored["sale__completed_at"] is not None:
                raise ValidationError("Историческую комиссию завершённой продажи изменять нельзя.")
        return super().save(*args, **kwargs)


class SaleCDItem(SaleItemBase):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="cd_items", verbose_name="Продажа")
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="sale_items", verbose_name="CD")

    class Meta:
        verbose_name = "позиция CD в продаже"
        verbose_name_plural = "позиции CD в продажах"
        constraints = [
            models.UniqueConstraint(fields=("sale", "cd"), name="unique_sale_cd_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sale_cd_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="sale_cd_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(unit_discount__gte=0, unit_discount__lte=models.F("unit_price")),
                name="sale_cd_discount_valid",
            ),
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="sale_cd_total_nonnegative"),
            models.CheckConstraint(
                condition=(
                    models.Q(avito_commission_enabled=False, avito_commission_amount=0)
                    | models.Q(avito_commission_enabled=True, avito_commission_amount__gte=1)
                ),
                name="sale_cd_avito_commission_consistent",
            ),
        ]


class SaleTechItem(SaleItemBase):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Продажа")
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, related_name="sale_items", verbose_name="Техника")

    class Meta:
        verbose_name = "позиция техники в продаже"
        verbose_name_plural = "позиции техники в продажах"
        constraints = [
            models.UniqueConstraint(fields=("sale", "tech"), name="unique_sale_tech_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sale_tech_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="sale_tech_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(unit_discount__gte=0, unit_discount__lte=models.F("unit_price")),
                name="sale_tech_discount_valid",
            ),
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="sale_tech_total_nonnegative"),
            models.CheckConstraint(
                condition=(
                    models.Q(avito_commission_enabled=False, avito_commission_amount=0)
                    | models.Q(avito_commission_enabled=True, avito_commission_amount__gte=1)
                ),
                name="sale_tech_avito_commission_consistent",
            ),
        ]


class SaleCustomItem(SaleItemBase):
    """Историческая строка продажи без связи с номенклатурой и складом."""

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="custom_items", verbose_name="Продажа")
    article_snapshot = models.CharField("Артикул", max_length=100, default="", blank=True)

    class Meta:
        verbose_name = "произвольная позиция продажи"
        verbose_name_plural = "произвольные позиции продаж"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sale_custom_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="sale_custom_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(unit_discount__gte=0, unit_discount__lte=models.F("unit_price")),
                name="sale_custom_discount_valid",
            ),
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="sale_custom_total_nonnegative"),
            models.CheckConstraint(
                condition=(
                    models.Q(avito_commission_enabled=False, avito_commission_amount=0)
                    | models.Q(avito_commission_enabled=True, avito_commission_amount__gte=1)
                ),
                name="sale_custom_avito_commission_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost_snapshot__isnull=False, unit_cost_snapshot__gte=0),
                name="sale_custom_cost_nonnegative",
            ),
            models.CheckConstraint(condition=~models.Q(product_name_snapshot=""), name="sale_custom_name_nonempty"),
        ]


class SaleConsignmentItem(models.Model):
    """Неизменяемый снимок партии реализации, проданной в составе обычной продажи."""

    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    sale = models.ForeignKey(
        Sale, on_delete=models.PROTECT, related_name="consignment_items", verbose_name="Продажа",
    )
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices)
    cd = models.ForeignKey(
        CD, on_delete=models.PROTECT, related_name="consignment_sale_items", null=True, blank=True,
    )
    tech = models.ForeignKey(
        Tech, on_delete=models.PROTECT, related_name="consignment_sale_items", null=True, blank=True,
    )
    platform = models.ForeignKey(
        SalesPlatform, on_delete=models.PROTECT, related_name="sale_items", verbose_name="Площадка",
    )
    source_stock_id = models.PositiveBigIntegerField("ID партии реализации")
    quantity = models.PositiveIntegerField("Количество")
    unit_price = models.DecimalField("Вознаграждение за единицу", max_digits=20, decimal_places=2)
    line_total = models.DecimalField("Сумма строки", max_digits=20, decimal_places=2)
    unit_cost_snapshot = models.DecimalField(
        "Себестоимость единицы на момент продажи", max_digits=20, decimal_places=2, editable=False,
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255)
    article_snapshot = models.CharField("Артикул", max_length=100)
    platform_name_snapshot = models.CharField("Площадка", max_length=255)

    class Meta:
        verbose_name = "позиция реализации в продаже"
        verbose_name_plural = "позиции реализации в продажах"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ), name="sale_consignment_exact_product",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sale_consignment_qty_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="sale_consignment_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_cost_snapshot__gte=0), name="sale_consignment_cost_nonnegative"),
            models.UniqueConstraint(
                fields=("sale", "product_kind", "source_stock_id"), name="unique_sale_consignment_stock",
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech
