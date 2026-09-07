import uuid

from django.conf import settings
from django.db import models

from catalog.models import CD, Tech
from partners.models import SalesPlatform
from warehouse.models import Warehouse


def temporary_sale_id():
    return f"TMP-{uuid.uuid4().hex}"


class Sale(models.Model):
    class PriceType(models.TextChoices):
        RETAIL = "retail", "Розничная"
        WHOLESALE = "wholesale", "Оптовая"
        YANDEX_MARKET = "yandex_market", "Яндекс Маркет"
        CONSIGNMENT = "consignment", "Реализация"

    class SaleType(models.TextChoices):
        RETAIL = "retail", "Розница"
        WHOLESALE_PICKUP = "wholesale_pickup", "Опт самовывоз"
        WHOLESALE_DELIVERY = "wholesale_delivery", "Опт доставка"
        AVITO = "avito", "Авито"
        YANDEX_MARKET = "yandex_market", "Яндексмаркет"
        CONSIGNMENT = "consignment", "Реализация"

    class PaymentMethod(models.TextChoices):
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
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_sales", verbose_name="Создал"
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    completed_at = models.DateTimeField("Завершена", null=True, blank=True, editable=False)
    total_amount = models.DecimalField("Сумма", max_digits=20, decimal_places=2, default=0, editable=False)

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
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="sale_total_nonnegative")
        ]

    @property
    def is_completed(self):
        return self.order_status == self.OrderStatus.DELIVERED and self.payment_status == self.PaymentStatus.PAID

    @property
    def is_postpay_editable(self):
        return (
            self.payment_method == self.PaymentMethod.CASH_POSTPAY
            and self.payment_status == self.PaymentStatus.UNPAID
            and self.order_status != self.OrderStatus.DELIVERED
        )

    @property
    def position_count(self):
        return self.cd_items.count() + self.tech_items.count()

    @property
    def total_units(self):
        return sum(item.quantity for item in self.cd_items.all()) + sum(
            item.quantity for item in self.tech_items.all()
        )

    def __str__(self):
        return self.visible_id

    def save(self, *args, **kwargs):
        """Разрешает только одно служебное преобразование TMP-id в постоянный номер продажи."""
        if self.pk:
            stored_id = type(self).objects.filter(pk=self.pk).values_list("visible_id", flat=True).first()
            if stored_id and not stored_id.startswith("TMP-") and stored_id != self.visible_id:
                from django.core.exceptions import ValidationError

                raise ValidationError("Номер созданной продажи изменять нельзя.")
        return super().save(*args, **kwargs)


class SaleItemBase(models.Model):
    quantity = models.PositiveIntegerField("Количество")
    unit_price = models.DecimalField("Цена единицы", max_digits=20, decimal_places=2)
    line_total = models.DecimalField("Сумма строки", max_digits=20, decimal_places=2)
    product_name_snapshot = models.CharField("Название товара", max_length=255)
    article_snapshot = models.CharField("Артикул", max_length=100)

    class Meta:
        abstract = True


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
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="sale_cd_total_nonnegative"),
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
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="sale_tech_total_nonnegative"),
        ]
