from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import Supplier


class Supply(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = "accepted", "Принята"

    accepted_at = models.DateTimeField("Принята", auto_now_add=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accepted_supplies", verbose_name="Принял")
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.ACCEPTED, editable=False)
    total_units = models.PositiveIntegerField("Физических единиц")
    goods_total_before_expenses = models.DecimalField("Товары до расходов", max_digits=20, decimal_places=2)
    expenses_total = models.DecimalField("Дополнительные расходы", max_digits=20, decimal_places=2)
    grand_total = models.DecimalField("Итого", max_digits=20, decimal_places=2)

    class Meta:
        ordering = ("-accepted_at", "-id")
        verbose_name = "поставка"
        verbose_name_plural = "поставки"
        constraints = [
            models.CheckConstraint(condition=models.Q(total_units__gt=0), name="supply_total_units_positive"),
            models.CheckConstraint(condition=models.Q(goods_total_before_expenses__gte=0), name="supply_goods_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(expenses_total__gte=0), name="supply_expenses_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(grand_total__gte=0), name="supply_grand_total_nonnegative"),
        ]

    @property
    def item_count(self):
        return self.cd_items.count() + self.tech_items.count()

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
