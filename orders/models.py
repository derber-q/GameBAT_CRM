from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import Supplier
from price.models import ProcurementPriceList, ProcurementPriceListItem
from warehouse.models import Warehouse


class TripAdditionReceipt(models.Model):
    """Идемпотентность добавления; финансовый учёт остаётся в штатных заказах."""
    key = models.UUIDField(primary_key=True, editable=False)
    batch = models.ForeignKey('SupplierOrderBatch', on_delete=models.PROTECT, related_name='addition_receipts')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    orders = models.ManyToManyField('CustomerProcurementOrder')
    created_at = models.DateTimeField(auto_now_add=True)


class TripOrderOperation(models.Model):
    """История обычных операций заказа; курсы и расчёт фиксируются при создании."""
    order = models.ForeignKey('CustomerProcurementOrder', on_delete=models.PROTECT, related_name='operations')
    sale = models.OneToOneField('sales.Sale', on_delete=models.PROTECT, null=True, blank=True, related_name='trip_operation')
    supply = models.OneToOneField('supplies.Supply', on_delete=models.PROTECT, null=True, blank=True, related_name='trip_operation')
    active = models.BooleanField(default=True, editable=False)
    usd_rub = models.DecimalField('Курс USD → RUB', max_digits=20, decimal_places=6)
    aed_rub = models.DecimalField('Курс AED → RUB', max_digits=20, decimal_places=6)
    calculation = models.JSONField('Снимок расчёта', editable=False)
    draft_key = models.UUIDField(unique=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')
        constraints = [
            models.UniqueConstraint(fields=('order',), condition=models.Q(active=True), name='one_active_trip_order_operation'),
            models.CheckConstraint(condition=(models.Q(sale__isnull=False, supply__isnull=True)
                | models.Q(sale__isnull=True, supply__isnull=False)), name='trip_operation_exactly_one_document'),
            models.CheckConstraint(condition=models.Q(usd_rub__gt=0, aed_rub__gt=0), name='trip_operation_positive_rates'),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            from django.core.exceptions import ValidationError
            stored = type(self).objects.get(pk=self.pk)
            fields = ('order_id', 'sale_id', 'supply_id', 'usd_rub', 'aed_rub', 'draft_key')
            if any(getattr(stored, field) != getattr(self, field) for field in fields):
                raise ValidationError('Курсы, расчёт и связи созданной операции изменять нельзя.')
            if stored.calculation != self.calculation and not getattr(self, '_pending_trip_cost_write', False):
                raise ValidationError('Снимок созданной операции изменять нельзя.')
            if not stored.active and self.active:
                raise ValidationError('Отменённую операцию нельзя активировать повторно.')
        return super().save(*args, **kwargs)


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
    class Purpose(models.TextChoices):
        CUSTOMER = "customer", "Клиентский заказ"
        STOCK = "stock", "Заказ на склад"

    purpose = models.CharField(
        "Назначение", max_length=12, choices=Purpose.choices,
        default=Purpose.CUSTOMER, db_default=Purpose.CUSTOMER, editable=False,
    )
    supply = models.OneToOneField(
        "supplies.Supply", on_delete=models.PROTECT, null=True, blank=True,
        related_name="procurement_order", verbose_name="Приход по заказу", editable=False,
    )
    trip = models.ForeignKey(
        "SupplierOrderBatch", on_delete=models.PROTECT, null=True, blank=True,
        related_name="trip_orders", verbose_name="Рейс", editable=False,
    )
    class Status(models.TextChoices):
        CREATED = "created", "Создан"
        CONFIRMED = "confirmed", "Подтверждён"
        RECEIVING = "receiving", "Принимается"
        COMPLETED = "completed", "Выполнен"

    recipient = models.CharField("Получатель", max_length=255)
    partner = models.ForeignKey("partners.Partner", on_delete=models.PROTECT, null=True, blank=True, related_name="procurement_orders", verbose_name="Заказчик")
    partner_name_snapshot = models.CharField("Заказчик на момент заказа", max_length=255, blank=True, db_default='')
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
    def is_stock_order(self):
        return self.purpose == self.Purpose.STOCK

    @property
    def fulfillment_label(self):
        if not self.trip_id:
            return self.get_status_display()
        from .arrival_models import TripArrival
        arrival = getattr(self,'_trip_arrival',None) if hasattr(self,'_trip_arrival') else TripArrival.objects.filter(trip_id=self.trip_id,arrived_at__isnull=False).first()
        if arrival:
            if self.pk in arrival.reviewed_orders and not self.arrival_rows.filter(actual_quantity__gt=0).exists():
                return 'Не поступил'
            return 'Выполнен' if self.status==self.Status.COMPLETED else 'В обработке' if self.fulfillment_processing else 'Доступен'
        if self.status == self.Status.COMPLETED:
            return 'Выполнен'
        if self.fulfillment_processing:
            return 'Привезён на склад'
        filtered = getattr(self, '_all_trip_invoices_accepted', None)
        if filtered is None:
            suppliers = set(self.trip.lines.filter(quantity__gt=0).values_list('supplier_id', flat=True))
            accepted = set(self.trip.invoice_flags.filter(accepted=True).values_list('supplier_id', flat=True))
            filtered = bool(suppliers) and suppliers.issubset(accepted)
        return 'Отфильтрован' if filtered else 'Принят'

    @property
    def fulfillment_processing(self):
        return bool(self.trip_id and self.status != self.Status.COMPLETED and
                    (self.supply_id or any(op.active for op in self.operations.all())))

    @property
    def fulfillment_completed(self):
        return bool(self.trip_id and self.status == self.Status.COMPLETED)

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
        ]

    @property
    def prepayment_line_total(self):
        return self.prepayment_unit_price * self.prepayment_quantity

    @property
    def quantity(self):
        return self.prepayment_quantity + self.postpayment_quantity

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


class SupplierOrderBatchQuerySet(models.QuerySet):
    def trips(self):
        # Старые подборки не имеют ни общего прайса, ни ключа создания рейса.
        return self.filter(models.Q(price_list__isnull=False) | models.Q(creation_key__isnull=False))


class SupplierOrderBatch(models.Model):
    objects = SupplierOrderBatchQuerySet.as_manager()
    price_list = models.ForeignKey(ProcurementPriceList, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="trips", verbose_name="Общий прайс", editable=False)
    name = models.CharField("Название рейса", max_length=255, blank=True, default="", db_default="")
    revision = models.PositiveIntegerField("Версия изменений", default=0, db_default=0, editable=False)
    creation_key = models.UUIDField(null=True, blank=True, unique=True, editable=False)
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
        return (f"Рейс №{self.pk}" + (f" · {self.name}" if self.name else "")) if self.is_trip else f"Подборка поставщикам №{self.pk}"

    @property
    def is_trip(self):
        return self.price_list_id is not None or self.creation_key is not None

    @property
    def is_completed(self):
        # Статус заказа следует за фактическим выполнением продажи/прихода и их отменой.
        orders = list(self.trip_orders.all() if self.is_trip else self.source_orders.all())
        return bool(orders) and all(order.status == CustomerProcurementOrder.Status.COMPLETED for order in orders)

    @property
    def completion_label(self):
        return 'Завершён' if self.is_completed else 'В работе'


class SupplierTripInvoice(models.Model):
    """Сохранённая отметка интерфейса рейса, без влияния на учётные сервисы."""
    batch = models.ForeignKey(SupplierOrderBatch, on_delete=models.CASCADE, related_name='invoice_flags')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='trip_invoice_flags')
    accepted = models.BooleanField('Инвойс принят', default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='+', editable=False)

    class Meta:
        default_permissions = ()
        verbose_name = 'отметка инвойса в рейсе'
        verbose_name_plural = 'отметки инвойсов в рейсах'
        constraints = [models.UniqueConstraint(fields=('batch', 'supplier'), name='unique_trip_supplier_invoice')]


class SupplierOrderBatchLine(ProductReferenceMixin):
    supplier_price_updated_at = models.DateTimeField(
        'Закупочная цена скорректирована', null=True, blank=True, editable=False,
    )
    price_list_item = models.ForeignKey(ProcurementPriceListItem, on_delete=models.PROTECT,
                                       null=True, blank=True, related_name="trip_lines", editable=False)
    price_supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="trip_price_lines", verbose_name="Источник цены", editable=False)
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
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="supplier_batch_quantity_nonnegative"),
            models.UniqueConstraint(fields=("batch", "supplier", "price_list_item", "price_supplier"),
                                    name="unique_trip_supplier_product_price"),
        ]

    def __str__(self):
        return f"{self.supplier}: {self.product_name_snapshot} × {self.quantity}"

    @property
    def total_aed(self):
        return self.supplier_price_aed_snapshot * self.quantity


class SupplierTripAllocation(models.Model):
    """Распределение строки поставщика между клиентскими позициями рейса."""
    line = models.ForeignKey(SupplierOrderBatchLine, on_delete=models.PROTECT, related_name="allocations")
    order_item = models.ForeignKey(CustomerProcurementOrderItem, on_delete=models.PROTECT, related_name="trip_allocations")
    prepayment_quantity = models.PositiveIntegerField(default=0)
    postpayment_quantity = models.PositiveIntegerField(default=0)
    prepayment_cap = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("line", "order_item"), name="unique_trip_line_customer_item")]

    @property
    def quantity(self):
        return self.prepayment_quantity + self.postpayment_quantity


class SupplierTripChange(models.Model):
    batch = models.ForeignKey(SupplierOrderBatch, on_delete=models.PROTECT, related_name="changes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    revision = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ("-created_at", "-id")


from .arrival_models import TripArrival, TripCostRow  # noqa: E402,F401
