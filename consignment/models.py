from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import SalesPlatform
from warehouse.models import Warehouse


class ConsignmentStockBase(models.Model):
    platform = models.ForeignKey(SalesPlatform, on_delete=models.PROTECT, verbose_name="Площадка")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, verbose_name="Склад-источник"
    )
    quantity = models.PositiveIntegerField("Количество", default=0)
    receivable_per_unit = models.DecimalField(
        "Сумма к получению за единицу", max_digits=16, decimal_places=2,
        default=0, validators=[MinValueValidator(0)],
    )

    class Meta:
        abstract = True

    @property
    def potential_receivable(self):
        return self.quantity * self.receivable_per_unit


class CDConsignmentStock(ConsignmentStockBase):
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="consignment_stocks", verbose_name="CD")

    class Meta:
        verbose_name = "остаток CD на реализации"
        verbose_name_plural = "остатки CD на реализации"
        permissions = [
            ("transfer_stock", "Может передавать товар на реализацию"),
            ("return_stock", "Может возвращать товар с реализации"),
            ("change_consignment_reward", "Может изменять вознаграждение на реализации"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("platform", "warehouse", "cd"), name="unique_cd_platform_warehouse_stock"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="cd_stock_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(receivable_per_unit__gte=0), name="cd_stock_receivable_nonnegative"),
        ]

    def __str__(self):
        return f"{self.platform}: {self.cd}"


class TechConsignmentStock(ConsignmentStockBase):
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, related_name="consignment_stocks", verbose_name="Техника")

    class Meta:
        verbose_name = "остаток техники на реализации"
        verbose_name_plural = "остатки техники на реализации"
        constraints = [
            models.UniqueConstraint(fields=("platform", "warehouse", "tech"), name="unique_tech_platform_warehouse_stock"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="tech_stock_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(receivable_per_unit__gte=0), name="tech_stock_receivable_nonnegative"),
        ]

    def __str__(self):
        return f"{self.platform}: {self.tech}"


class ConsignmentMovement(models.Model):
    """Неизменяемый документ передачи на реализацию или возврата."""

    class OperationType(models.TextChoices):
        TRANSFER = "transfer", "Передача на реализацию"
        RETURN = "return", "Возврат с реализации"

    operation_type = models.CharField("Операция", max_length=16, choices=OperationType.choices, editable=False)
    platform = models.ForeignKey(
        SalesPlatform, on_delete=models.PROTECT, related_name="consignment_movements",
        editable=False, verbose_name="Площадка",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="consignment_movements",
        editable=False, verbose_name="Склад",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="consignment_movements",
        editable=False, verbose_name="Выполнил",
    )
    created_at = models.DateTimeField("Дата и время", auto_now_add=True, editable=False)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "операция реализации"
        verbose_name_plural = "операции реализации"

    @property
    def position_count(self):
        return self.items.count()

    @property
    def total_units(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def number(self):
        return f"{self.pk:06d}"

    @property
    def action_label(self):
        return f"{self.get_operation_type_display()} №{self.number}"

    def __str__(self):
        return self.action_label


class ConsignmentMovementItem(models.Model):
    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    movement = models.ForeignKey(
        ConsignmentMovement, on_delete=models.PROTECT, related_name="items", verbose_name="Операция"
    )
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices, editable=False)
    cd = models.ForeignKey(
        CD, on_delete=models.PROTECT, related_name="consignment_movement_items",
        null=True, blank=True, editable=False, verbose_name="CD",
    )
    tech = models.ForeignKey(
        Tech, on_delete=models.PROTECT, related_name="consignment_movement_items",
        null=True, blank=True, editable=False, verbose_name="Техника",
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    product_sku_snapshot = models.CharField("Артикул", max_length=100, editable=False)
    quantity = models.PositiveIntegerField("Количество", editable=False)
    receivable_per_unit = models.DecimalField(
        "Сумма к получению за единицу", max_digits=16, decimal_places=2,
        validators=[MinValueValidator(0)], editable=False,
    )
    warehouse_quantity_before = models.PositiveIntegerField("Остаток склада до", editable=False)
    warehouse_quantity_after = models.PositiveIntegerField("Остаток склада после", editable=False)
    consignment_quantity_before = models.PositiveIntegerField("На реализации до", editable=False)
    consignment_quantity_after = models.PositiveIntegerField("На реализации после", editable=False)

    class Meta:
        ordering = ("id",)
        verbose_name = "позиция операции реализации"
        verbose_name_plural = "позиции операций реализации"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="consignment_movement_item_quantity_positive"),
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="consignment_movement_item_exact_product",
            ),
            models.UniqueConstraint(
                fields=("movement", "cd"), condition=models.Q(cd__isnull=False),
                name="unique_consignment_movement_cd",
            ),
            models.UniqueConstraint(
                fields=("movement", "tech"), condition=models.Q(tech__isnull=False),
                name="unique_consignment_movement_tech",
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    def __str__(self):
        return f"{self.movement}: {self.product_name_snapshot}"
