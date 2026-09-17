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
    weight_transport_cost = models.DecimalField(
        "Транспортные расходы по весу", max_digits=20, decimal_places=2,
        default=0, validators=[MinValueValidator(0)],
    )
    total_weight_grams = models.PositiveBigIntegerField(
        "Общий вес поставки, г", null=True, blank=True, editable=False
    )
    grand_total = models.DecimalField("Итого", max_digits=20, decimal_places=2)
    cancelled_at = models.DateTimeField("Отменена", null=True, blank=True, editable=False)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cancelled_supplies",
        verbose_name="Отменил", null=True, blank=True, editable=False,
    )
    cancellation_comment = models.TextField("Причина отмены", blank=True, editable=False)
    revision_number = models.PositiveIntegerField("Текущая редакция", default=1, editable=False)
    last_revised_at = models.DateTimeField("Последнее изменение", null=True, blank=True, editable=False)
    last_revised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="revised_supplies",
        verbose_name="Последним изменил", null=True, blank=True, editable=False,
    )

    class Meta:
        ordering = ("-accepted_at", "-id")
        verbose_name = "поставка"
        verbose_name_plural = "поставки"
        permissions = [
            ("cancel_supply", "Может отменять принятые приходы"),
            ("edit_accepted_supply", "Может редактировать принятые приходы"),
            ("finalize_supply", "Может выполнять финализацию прихода"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_units__gt=0), name="supply_total_units_positive"),
            models.CheckConstraint(condition=models.Q(goods_total_before_expenses__gte=0), name="supply_goods_total_nonnegative"),
            models.CheckConstraint(condition=models.Q(expenses_total__gte=0), name="supply_expenses_total_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(weight_transport_cost__gte=0),
                name="supply_weight_transport_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(total_weight_grams__gt=0)
                    | models.Q(total_weight_grams__isnull=True)
                ),
                name="supply_total_weight_positive_or_legacy",
            ),
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
    weight_grams_snapshot = models.PositiveIntegerField(
        "Вес единицы на момент прихода, г", null=True, blank=True, editable=False
    )
    line_weight_grams = models.PositiveBigIntegerField(
        "Вес строки, г", null=True, blank=True, editable=False
    )
    allocated_transport_cost = models.DecimalField(
        "Транспортные расходы строки", max_digits=20, decimal_places=2, default=0,
    )
    transport_cost_per_unit = models.DecimalField(
        "Транспортные расходы на единицу", max_digits=20, decimal_places=6, default=0,
    )
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
            models.CheckConstraint(condition=models.Q(weight_grams_snapshot__gt=0) | models.Q(weight_grams_snapshot__isnull=True), name="supply_cd_weight_positive_or_legacy"),
            models.CheckConstraint(condition=models.Q(line_weight_grams__gt=0) | models.Q(line_weight_grams__isnull=True), name="supply_cd_line_weight_positive_or_legacy"),
            models.CheckConstraint(condition=models.Q(allocated_transport_cost__gte=0), name="supply_cd_transport_nonnegative"),
            models.CheckConstraint(condition=models.Q(transport_cost_per_unit__gte=0), name="supply_cd_transport_unit_nonnegative"),
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
            models.CheckConstraint(condition=models.Q(weight_grams_snapshot__gt=0) | models.Q(weight_grams_snapshot__isnull=True), name="supply_tech_weight_positive_or_legacy"),
            models.CheckConstraint(condition=models.Q(line_weight_grams__gt=0) | models.Q(line_weight_grams__isnull=True), name="supply_tech_line_weight_positive_or_legacy"),
            models.CheckConstraint(condition=models.Q(allocated_transport_cost__gte=0), name="supply_tech_transport_nonnegative"),
            models.CheckConstraint(condition=models.Q(transport_cost_per_unit__gte=0), name="supply_tech_transport_unit_nonnegative"),
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


class SupplyRevision(models.Model):
    supply = models.ForeignKey(
        Supply, on_delete=models.PROTECT, related_name="revisions", verbose_name="Приход"
    )
    revision_number = models.PositiveIntegerField("Номер редакции", editable=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="supply_revisions",
        verbose_name="Автор изменения", editable=False,
    )
    reason = models.TextField("Причина изменения", editable=False)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="supply_revision_snapshots",
        verbose_name="Склад", editable=False,
    )
    accepted_at_snapshot = models.DateTimeField("Историческая дата прихода", editable=False)
    accepted_by_name_snapshot = models.CharField("Принял", max_length=255, editable=False)
    total_units = models.PositiveIntegerField("Физических единиц", editable=False)
    goods_total_before_expenses = models.DecimalField(
        "Товары до расходов", max_digits=20, decimal_places=2, editable=False
    )
    expenses_total = models.DecimalField(
        "Дополнительные расходы", max_digits=20, decimal_places=2, editable=False
    )
    weight_transport_cost = models.DecimalField(
        "Транспортные расходы по весу", max_digits=20, decimal_places=2, editable=False
    )
    total_weight_grams = models.PositiveBigIntegerField(
        "Общий вес, г", null=True, blank=True, editable=False
    )
    grand_total = models.DecimalField("Итого", max_digits=20, decimal_places=2, editable=False)
    diff_summary = models.JSONField("Сводка изменений", default=dict, blank=True, editable=False)

    class Meta:
        ordering = ("-revision_number", "-id")
        verbose_name = "редакция принятого прихода"
        verbose_name_plural = "редакции принятых приходов"
        constraints = [
            models.UniqueConstraint(
                fields=("supply", "revision_number"), name="unique_supply_revision_number"
            ),
        ]

    def __str__(self):
        return f"Приход №{self.supply_id}, редакция {self.revision_number}"


class SupplyRevisionItem(models.Model):
    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    revision = models.ForeignKey(
        SupplyRevision, on_delete=models.CASCADE, related_name="items", verbose_name="Редакция"
    )
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices, editable=False)
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, null=True, blank=True, editable=False)
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, null=True, blank=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, editable=False)
    quantity = models.PositiveIntegerField("Количество", editable=False)
    purchase_unit_cost = models.DecimalField("Закупка за единицу", max_digits=20, decimal_places=6, editable=False)
    allocated_expense_per_unit = models.DecimalField("Обычный расход за единицу", max_digits=20, decimal_places=6, editable=False)
    weight_grams_snapshot = models.PositiveIntegerField("Вес единицы, г", null=True, blank=True, editable=False)
    line_weight_grams = models.PositiveBigIntegerField("Вес строки, г", null=True, blank=True, editable=False)
    allocated_transport_cost = models.DecimalField("Транспорт строки", max_digits=20, decimal_places=2, editable=False)
    transport_cost_per_unit = models.DecimalField("Транспорт за единицу", max_digits=20, decimal_places=6, editable=False)
    effective_unit_cost = models.DecimalField("Итог за единицу", max_digits=20, decimal_places=6, editable=False)
    base_line_total = models.DecimalField("Закупка строки", max_digits=20, decimal_places=2, editable=False)
    final_line_total = models.DecimalField("Итого строки", max_digits=20, decimal_places=2, editable=False)
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    product_sku_snapshot = models.CharField("Артикул", max_length=100, blank=True, editable=False)
    supplier_letter_snapshot = models.CharField("Буква поставщика", max_length=8, editable=False)
    supplier_color_snapshot = models.CharField("Цвет поставщика", max_length=7, editable=False)
    supplier_name_snapshot = models.CharField("Название поставщика", max_length=255, editable=False)

    class Meta:
        ordering = ("id",)
        verbose_name = "позиция редакции прихода"
        verbose_name_plural = "позиции редакций приходов"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="supply_revision_item_exact_product",
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech


class SupplyRevisionExpense(models.Model):
    revision = models.ForeignKey(
        SupplyRevision, on_delete=models.CASCADE, related_name="expenses", verbose_name="Редакция"
    )
    name = models.CharField("Название расхода", max_length=255, editable=False)
    amount = models.DecimalField("Сумма", max_digits=20, decimal_places=2, editable=False)

    class Meta:
        ordering = ("id",)
        verbose_name = "расход редакции прихода"
        verbose_name_plural = "расходы редакций приходов"


class SupplyFinalization(models.Model):
    """Неизменяемая история перераспределения глобальной себестоимости."""

    class Status(models.TextChoices):
        APPLIED = "applied", "Применена"
        SUPERSEDED = "superseded", "Утратила актуальность после редакции прихода"

    supply = models.ForeignKey(
        Supply, on_delete=models.PROTECT, related_name="finalizations", verbose_name="Приход"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="supply_finalizations", verbose_name="Выполнил", editable=False,
    )
    created_at = models.DateTimeField("Дата и время", auto_now_add=True, editable=False)
    supply_revision_number = models.PositiveIntegerField("Редакция прихода", editable=False)
    total_penalty_before_distribution = models.DecimalField(
        "Неустойка до автораспределения", max_digits=20, decimal_places=2, editable=False
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices,
        default=Status.APPLIED, editable=False,
    )
    superseded_at = models.DateTimeField(
        "Утратила актуальность", null=True, blank=True, editable=False
    )
    superseded_by_revision_number = models.PositiveIntegerField(
        "Заменена редакцией", null=True, blank=True, editable=False
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "финализация прихода"
        verbose_name_plural = "финализации приходов"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="applied", superseded_at__isnull=True,
                        superseded_by_revision_number__isnull=True,
                    )
                    | models.Q(
                        status="superseded", superseded_at__isnull=False,
                        superseded_by_revision_number__isnull=False,
                    )
                ),
                name="supply_finalization_status_consistent",
            ),
        ]

    def __str__(self):
        return f"Финализация прихода №{self.supply_id}"


class SupplyFinalizationItem(models.Model):
    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    class ChangeSource(models.TextChoices):
        MANUAL = "manual", "Вручную"
        AUTO_DISTRIBUTED = "auto", "Автораспределение"

    finalization = models.ForeignKey(
        SupplyFinalization, on_delete=models.PROTECT,
        related_name="items", verbose_name="Финализация"
    )
    product_kind = models.CharField(
        "Тип товара", max_length=8, choices=ProductKind.choices, editable=False
    )
    cd = models.ForeignKey(
        CD, on_delete=models.PROTECT, related_name="supply_finalization_items",
        null=True, blank=True, editable=False, verbose_name="CD",
    )
    tech = models.ForeignKey(
        Tech, on_delete=models.PROTECT, related_name="supply_finalization_items",
        null=True, blank=True, editable=False, verbose_name="Техника",
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    product_sku_snapshot = models.CharField("Артикул", max_length=100, blank=True, editable=False)
    global_quantity_snapshot = models.PositiveIntegerField("Глобальный остаток", editable=False)
    old_global_cost = models.DecimalField(
        "Старая себестоимость", max_digits=20, decimal_places=2, editable=False
    )
    new_global_cost = models.DecimalField(
        "Новая себестоимость", max_digits=20, decimal_places=2, editable=False
    )
    difference_per_unit = models.DecimalField(
        "Изменение на единицу", max_digits=20, decimal_places=2, editable=False
    )
    value_difference = models.DecimalField(
        "Изменение стоимости остатка", max_digits=20, decimal_places=2, editable=False
    )
    change_source = models.CharField(
        "Способ изменения", max_length=8, choices=ChangeSource.choices, editable=False
    )

    class Meta:
        ordering = ("product_kind", "product_name_snapshot", "id")
        verbose_name = "позиция финализации прихода"
        verbose_name_plural = "позиции финализации приходов"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="supply_finalization_item_exact_product",
            ),
            models.UniqueConstraint(
                fields=("finalization", "cd"), condition=models.Q(cd__isnull=False),
                name="unique_supply_finalization_cd",
            ),
            models.UniqueConstraint(
                fields=("finalization", "tech"), condition=models.Q(tech__isnull=False),
                name="unique_supply_finalization_tech",
            ),
            models.CheckConstraint(
                condition=models.Q(old_global_cost__gte=0),
                name="supply_finalization_old_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(new_global_cost__gte=0),
                name="supply_finalization_new_cost_nonnegative",
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    def __str__(self):
        return f"{self.finalization}: {self.product_name_snapshot}"
