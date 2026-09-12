from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import Supplier
from warehouse.models import Warehouse


class Supply(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Принята"
        CANCELLED = "cancelled", "Отменена"

    accepted_at = models.DateTimeField("Принята", auto_now_add=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accepted_supplies", verbose_name="Принял")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="supplies", verbose_name="Склад поступления"
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.ACCEPTED, editable=False)
    total_units = models.PositiveIntegerField("Физических единиц")
    goods_total_before_expenses = models.DecimalField("Товары до расходов", max_digits=20, decimal_places=2)
    expenses_total = models.DecimalField("Дополнительные расходы", max_digits=20, decimal_places=2)
    grand_total = models.DecimalField("Итого", max_digits=20, decimal_places=2)
    cancelled_at = models.DateTimeField("Отменена", null=True, blank=True, editable=False)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cancelled_supplies",
        verbose_name="Отменил", null=True, blank=True, editable=False,
    )
    cancellation_comment = models.TextField("Причина отмены", blank=True, editable=False)

    class Meta:
        ordering = ("-accepted_at", "-id")
        verbose_name = "поставка"
        verbose_name_plural = "поставки"
        permissions = [("cancel_supply", "Может отменять принятые приходы")]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_units__gt=0), name="supply_total_units_positive"),
            models.CheckConstraint(condition=models.Q(goods_total_before_expenses__gte=0), name="supply_goods_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(expenses_total__gte=0), name="supply_expenses_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="supply_grand_total_nonnegative"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="accepted", cancelled_at__isnull=True,
                        cancelled_by__isnull=True, cancellation_comment="",
                    )
                    | (
                        models.Q(status="cancelled", cancelled_at__isnull=False, cancelled_by__isnull=False)
                        & ~models.Q(cancellation_comment="")
                    )
                ),
                name="supply_cancellation_fields_consistent",
            ),
        ]

    @property
    def item_count(self):
        return self.cd_items.count() + self.tech_items.count()

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    def __str__(self):
        return f"Поставка №{self.pk}"


class SupplyItemBase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Поставщик")
    quantity = models.PositiveIntegerField("Количество")
    purchase_unit_cost = models.DecimalField("Закупочная цена единицы", max_digits=20, decimal_places=6)
    allocated_expense_per_unit = models.DecimalField("Расход на единицу", max_digits=20, decimal_places=6)
    effective_unit_cost = models.DecimalField("Итоговая цена единицы", max_digits=20, decimal_places=6)
    base_line_total = models.DecimalField("Закупочная сумма строки", max_digits=20, decimal_places=2)
    final_line_total = models.DecimalField("Итоговая сумма строки", max_digits=20, decimal_places=2)
    product_name_snapshot = models.CharField("Название товара", max_length=255)
    product_sku_snapshot = models.CharField("Артикул", max_length=100)
    supplier_letter_snapshot = models.CharField("Буква поставщика", max_length=8)
    supplier_color_snapshot = models.CharField("Цвет поставщика", max_length=7)
    supplier_name_snapshot = models.CharField("Название поставщика", max_length=255)

    class Meta:
        abstract = True


class SupplyCDItem(SupplyItemBase):
    supply = models.ForeignKey(Supply, on_delete=models.PROTECT, related_name="cd_items", verbose_name="Поставка")
    product = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="supply_items", verbose_name="CD")

    class Meta:
        verbose_name = "позиция CD в поставке"
        verbose_name_plural = "позиции CD в поставках"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="supply_cd_quantity_positive"),
            models.CheckConstraint(condition=models.Q(purchase_unit_cost__gte=0), name="supply_cd_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(allocated_expense_per_unit__gte=0), name="supply_cd_allocated_nonnegative"),
            models.CheckConstraint(condition=models.Q(effective_unit_cost__gte=0), name="supply_cd_effective_nonnegative"),
            models.CheckConstraint(condition=models.Q(base_line_total__gte=0), name="supply_cd_base_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(final_line_total__gte=0), name="supply_cd_final_total_nonnegative"),
        ]


class SupplyTechItem(SupplyItemBase):
    supply = models.ForeignKey(Supply, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Поставка")
    product = models.ForeignKey(Tech, on_delete=models.PROTECT, related_name="supply_items", verbose_name="Техника")

    class Meta:
        verbose_name = "позиция техники в поставке"
        verbose_name_plural = "позиции техники в поставках"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="supply_tech_quantity_positive"),
            models.CheckConstraint(condition=models.Q(purchase_unit_cost__gte=0), name="supply_tech_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(allocated_expense_per_unit__gte=0), name="supply_tech_allocated_nonnegative"),
            models.CheckConstraint(condition=models.Q(effective_unit_cost__gte=0), name="supply_tech_effective_nonnegative"),
            models.CheckConstraint(condition=models.Q(base_line_total__gte=0), name="supply_tech_base_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(final_line_total__gte=0), name="supply_tech_final_total_nonnegative"),
        ]


class SupplyCostCalculation(models.Model):
    """Исторический снимок средневзвешенного расчёта для одного товара."""

    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    supply = models.ForeignKey(
        Supply, on_delete=models.PROTECT, related_name="cost_calculations", verbose_name="Поставка"
    )
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices, editable=False)
    cd = models.ForeignKey(
        CD, on_delete=models.PROTECT, related_name="supply_cost_calculations",
        null=True, blank=True, editable=False, verbose_name="CD",
    )
    tech = models.ForeignKey(
        Tech, on_delete=models.PROTECT, related_name="supply_cost_calculations",
        null=True, blank=True, editable=False, verbose_name="Техника",
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    product_sku_snapshot = models.CharField("Артикул", max_length=100, editable=False)
    old_owned_quantity = models.PositiveIntegerField("Количество до поставки", editable=False)
    old_unit_cost = models.DecimalField(
        "Себестоимость до поставки", max_digits=20, decimal_places=2, editable=False
    )
    old_inventory_value = models.DecimalField(
        "Стоимость остатка до поставки", max_digits=20, decimal_places=6, editable=False
    )
    incoming_quantity = models.PositiveIntegerField("Поступило", editable=False)
    incoming_value = models.DecimalField(
        "Стоимость поступления с расходами", max_digits=20, decimal_places=6, editable=False
    )
    resulting_quantity = models.PositiveIntegerField("Количество после поставки", editable=False)
    resulting_value = models.DecimalField(
        "Общая стоимость после поставки", max_digits=20, decimal_places=6, editable=False
    )
    resulting_unit_cost = models.DecimalField(
        "Новая себестоимость", max_digits=20, decimal_places=2, editable=False
    )

    class Meta:
        ordering = ("id",)
        verbose_name = "расчёт себестоимости поставки"
        verbose_name_plural = "расчёты себестоимости поставок"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="supply_cost_calculation_exact_product",
            ),
            models.UniqueConstraint(
                fields=("supply", "cd"), condition=models.Q(cd__isnull=False),
                name="unique_supply_cd_cost_calculation",
            ),
            models.UniqueConstraint(
                fields=("supply", "tech"), condition=models.Q(tech__isnull=False),
                name="unique_supply_tech_cost_calculation",
            ),
            models.CheckConstraint(
                condition=models.Q(incoming_quantity__gt=0), name="supply_cost_incoming_quantity_positive"
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    def __str__(self):
        return f"{self.supply}: {self.product_name_snapshot}"


class SupplyExpense(models.Model):
    supply = models.ForeignKey(Supply, on_delete=models.PROTECT, related_name="expenses", verbose_name="Поставка")
    name = models.CharField("Название расхода", max_length=255)
    amount = models.DecimalField("Сумма", max_digits=20, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "дополнительный расход"
        verbose_name_plural = "дополнительные расходы"
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="supply_expense_nonnegative")]

    def __str__(self):
        return f"{self.name}: {self.amount}"
