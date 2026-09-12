from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import Supplier
from price.models import ProcurementPriceList, ProcurementPriceListItem
from warehouse.models import Warehouse


class ProductReferenceMixin(models.Model):
    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices, editable=False)
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, null=True, blank=True, editable=False)
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    @property
    def product_id(self):
        return self.cd_id if self.product_kind == self.ProductKind.CD else self.tech_id


class CustomerProcurementOrder(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Создан"
        CONFIRMED = "confirmed", "Подтверждён"
        RECEIVING = "receiving", "Принимается"
        COMPLETED = "completed", "Выполнен"

    recipient = models.CharField("Получатель", max_length=255)
    comment = models.TextField("Комментарий", blank=True)
    price_list = models.ForeignKey(
        ProcurementPriceList, on_delete=models.PROTECT, related_name="customer_orders",
        verbose_name="Исходный закупочный прайс", editable=False,
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.CREATED, editable=False
    )
    payment_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="customer_procurement_orders",
        verbose_name="Склад оплаты", null=True, blank=True, editable=False,
    )
    prepayment_total = models.DecimalField(
        "Предоплата", max_digits=20, decimal_places=2, default=0, editable=False
    )
    postpayment_total = models.DecimalField(
        "Постоплата", max_digits=20, decimal_places=2, default=0, editable=False
    )
    grand_total = models.DecimalField("Итого", max_digits=20, decimal_places=2, default=0, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_customer_procurement_orders", verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "клиентский закупочный заказ"
        verbose_name_plural = "клиентские закупочные заказы"
        permissions = [
            ("view_orders", "Заказы: просмотр списка"),
            ("view_order_detail", "Заказы: просмотр заказа"),
            ("create_order", "Заказы: создание"),
            ("edit_created_order", "Заказы: изменение созданного заказа"),
            ("confirm_order", "Заказы: подтверждение и предоплата"),
            ("start_receiving", "Заказы: начало приёмки"),
            ("edit_receiving_order", "Заказы: корректировка при приёмке"),
            ("complete_order", "Заказы: выполнение и постоплата"),
            ("view_order_adjustments", "Заказы: просмотр корректировок"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(prepayment_total__gte=0), name="order_prepayment_nonnegative"),
            models.CheckConstraint(condition=models.Q(postpayment_total__gte=0), name="order_postpayment_nonnegative"),
            models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="order_grand_total_nonnegative"),
        ]

    @property
    def total_units(self):
        return sum(item.prepayment_quantity + item.postpayment_quantity for item in self.items.all())

    def __str__(self):
        return f"Заказ №{self.pk} — {self.recipient}"


class CustomerProcurementOrderItem(ProductReferenceMixin):
    order = models.ForeignKey(
        CustomerProcurementOrder, on_delete=models.PROTECT, related_name="items", verbose_name="Заказ"
    )
    price_list_item = models.ForeignKey(
        ProcurementPriceListItem, on_delete=models.PROTECT, related_name="order_items",
        verbose_name="Позиция исходного прайса", editable=False,
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    article_snapshot = models.CharField("Артикул", max_length=100, editable=False)
    selected_supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="customer_order_items",
        verbose_name="Выбранный поставщик", editable=False,
    )
    supplier_price_aed_snapshot = models.DecimalField(
        "Цена поставщика, AED", max_digits=20, decimal_places=6, editable=False
    )
    prepayment_unit_price = models.DecimalField(
        "Цена предоплаты", max_digits=20, decimal_places=2, editable=False
    )
    postpayment_unit_price = models.DecimalField(
        "Цена постоплаты", max_digits=20, decimal_places=2, editable=False
    )
    prepayment_quantity = models.PositiveIntegerField("Количество по предоплате", default=0)
    postpayment_quantity = models.PositiveIntegerField("Количество по постоплате", default=0)

    class Meta:
        ordering = ("product_name_snapshot", "id")
        verbose_name = "позиция клиентского закупочного заказа"
        verbose_name_plural = "позиции клиентского закупочного заказа"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="customer_order_item_exact_product",
            ),
            models.UniqueConstraint(fields=("order", "price_list_item"), name="unique_order_price_list_item"),
            models.CheckConstraint(
                condition=models.Q(prepayment_quantity__gt=0) | models.Q(postpayment_quantity__gt=0),
                name="customer_order_item_quantity_positive",
            ),
        ]

    @property
    def prepayment_line_total(self):
        return self.prepayment_unit_price * self.prepayment_quantity

    @property
    def postpayment_line_total(self):
        return self.postpayment_unit_price * self.postpayment_quantity

    @property
    def line_total(self):
        return self.prepayment_line_total + self.postpayment_line_total

    def __str__(self):
        return self.product_name_snapshot


class CustomerOrderStatusEvent(models.Model):
    order = models.ForeignKey(
        CustomerProcurementOrder, on_delete=models.PROTECT, related_name="status_events", verbose_name="Заказ"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Пользователь")
    old_status = models.CharField("Предыдущий статус", max_length=20, choices=CustomerProcurementOrder.Status.choices)
    new_status = models.CharField("Новый статус", max_length=20, choices=CustomerProcurementOrder.Status.choices)
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "смена статуса закупочного заказа"
        verbose_name_plural = "смены статусов закупочных заказов"


class OrderAdjustment(models.Model):
    order = models.ForeignKey(
        CustomerProcurementOrder, on_delete=models.PROTECT, related_name="adjustments", verbose_name="Заказ"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Пользователь")
    created_at = models.DateTimeField("Дата", auto_now_add=True)
    comment = models.TextField("Комментарий")
    refund_amount = models.DecimalField(
        "Сумма возврата", max_digits=20, decimal_places=2, default=0, editable=False
    )

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "корректировка закупочного заказа"
        verbose_name_plural = "корректировки закупочных заказов"


class OrderAdjustmentChange(models.Model):
    adjustment = models.ForeignKey(
        OrderAdjustment, on_delete=models.PROTECT, related_name="changes", verbose_name="Корректировка"
    )
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductReferenceMixin.ProductKind.choices)
    product_id_snapshot = models.PositiveBigIntegerField("ID товара")
    product_name_snapshot = models.CharField("Название товара", max_length=255)
    field_name = models.CharField("Поле", max_length=40)
    old_value = models.PositiveIntegerField("Было")
    new_value = models.PositiveIntegerField("Стало")

    class Meta:
        ordering = ("id",)
        verbose_name = "изменение в корректировке заказа"
        verbose_name_plural = "изменения в корректировке заказа"


class SupplierOrderBatch(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="supplier_order_batches", verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    source_orders = models.ManyToManyField(
        CustomerProcurementOrder, related_name="supplier_order_batches", verbose_name="Исходные заказы"
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "подборка заказов поставщикам"
        verbose_name_plural = "подборки заказов поставщикам"
        permissions = [("generate_supplier_orders", "Заказы: формирование заказов поставщикам")]

    def __str__(self):
        return f"Подборка поставщикам №{self.pk}"


class SupplierOrderBatchLine(ProductReferenceMixin):
    batch = models.ForeignKey(
        SupplierOrderBatch, on_delete=models.PROTECT, related_name="lines", verbose_name="Подборка"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="order_batch_lines", verbose_name="Поставщик"
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    article_snapshot = models.CharField("Артикул", max_length=100, editable=False)
    quantity = models.PositiveIntegerField("Количество")
    supplier_price_aed_snapshot = models.DecimalField(
        "Цена поставщика, AED", max_digits=20, decimal_places=6, editable=False
    )

    class Meta:
        ordering = ("supplier__name", "product_name_snapshot", "id")
        verbose_name = "строка заказа поставщику"
        verbose_name_plural = "строки заказов поставщикам"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="supplier_batch_line_exact_product",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="supplier_batch_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.supplier}: {self.product_name_snapshot} × {self.quantity}"
