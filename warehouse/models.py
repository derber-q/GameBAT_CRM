from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import CD, Tech


class Warehouse(models.Model):
    name = models.CharField("Название", max_length=255, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "склад"
        verbose_name_plural = "склады"
        permissions = [
            ("view_global_stock", "Может просматривать общие остатки"),
            ("view_warehouse_stock", "Может просматривать остатки отдельного склада"),
            ("change_storage_location", "Может изменять места хранения товаров"),
        ]

    def __str__(self):
        return self.name


class WarehouseStockBase(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, verbose_name="Склад")
    quantity = models.PositiveIntegerField("Количество", default=0)

    class Meta:
        abstract = True


class WarehouseStorageLocation(models.Model):
    """Каноническое физическое место, уникальное внутри конкретного склада."""
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="storage_locations", verbose_name="Склад"
    )
    room = models.CharField("Помещение", max_length=1)
    rack = models.PositiveIntegerField("Стеллаж")
    shelf = models.PositiveIntegerField("Полка")
    columns = models.JSONField("Столбцы", default=list, blank=True)
    canonical_value = models.CharField("Каноническое значение", max_length=255, editable=False)

    class Meta:
        ordering = ("room", "rack", "shelf", "canonical_value", "id")
        verbose_name = "место хранения на складе"
        verbose_name_plural = "места хранения на складах"
        constraints = [
            models.UniqueConstraint(
                fields=("warehouse", "canonical_value"), name="unique_storage_location_per_warehouse"
            ),
            models.CheckConstraint(condition=models.Q(rack__gt=0), name="storage_location_rack_positive"),
            models.CheckConstraint(condition=models.Q(shelf__gt=0), name="storage_location_shelf_positive"),
        ]
        indexes = [
            models.Index(fields=("warehouse", "room", "rack", "shelf"), name="storage_location_lookup"),
        ]

    def _normalise_components(self):
        from .storage_locations import StorageLocationValue

        try:
            columns = tuple(sorted({int(value) for value in (self.columns or [])}))
            value = StorageLocationValue(
                room=str(self.room or "").upper(), rack=int(self.rack), shelf=int(self.shelf), columns=columns,
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("Некорректные компоненты места хранения.") from exc
        if len(value.room) != 1 or not ("A" <= value.room <= "Z"):
            raise ValidationError({"room": "Укажите одну латинскую букву A–Z."})
        if value.rack <= 0 or value.shelf <= 0 or any(column <= 0 for column in value.columns):
            raise ValidationError("Стеллаж, полка и столбцы должны быть положительными целыми числами.")
        self.room = value.room
        self.rack = value.rack
        self.shelf = value.shelf
        self.columns = list(value.columns)
        self.canonical_value = value.canonical

    def full_clean(self, *args, **kwargs):
        self._normalise_components()
        return super().full_clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.warehouse}: {self.canonical_value}"


class CDWarehouseStock(WarehouseStockBase):
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="cd_stocks", verbose_name="Склад"
    )
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="warehouse_stocks", verbose_name="CD")

    class Meta:
        verbose_name = "остаток CD на складе"
        verbose_name_plural = "остатки CD на складах"
        constraints = [
            models.UniqueConstraint(fields=("warehouse", "cd"), name="unique_cd_warehouse_stock"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="cd_warehouse_quantity_nonnegative"),
        ]

    def __str__(self):
        return f"{self.warehouse}: {self.cd}"


class TechWarehouseStock(WarehouseStockBase):
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="tech_stocks", verbose_name="Склад"
    )
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, related_name="warehouse_stocks", verbose_name="Техника")

    class Meta:
        verbose_name = "остаток техники на складе"
        verbose_name_plural = "остатки техники на складах"
        constraints = [
            models.UniqueConstraint(fields=("warehouse", "tech"), name="unique_tech_warehouse_stock"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="tech_warehouse_quantity_nonnegative"),
        ]

    def __str__(self):
        return f"{self.warehouse}: {self.tech}"


class WarehouseStorageAssignmentBase(models.Model):
    location = models.ForeignKey(
        WarehouseStorageLocation, on_delete=models.PROTECT, verbose_name="Место хранения"
    )
    position = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        abstract = True
        ordering = ("position", "id")

    def clean(self):
        super().clean()
        if self.location_id and self.stock_id and self.location.warehouse_id != self.stock.warehouse_id:
            raise ValidationError("Место хранения и товарный остаток должны относиться к одному складу.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CDWarehouseStorageAssignment(WarehouseStorageAssignmentBase):
    stock = models.ForeignKey(
        CDWarehouseStock, on_delete=models.CASCADE, related_name="storage_assignments",
        verbose_name="Остаток CD",
    )
    location = models.ForeignKey(
        WarehouseStorageLocation, on_delete=models.PROTECT, related_name="cd_assignments",
        verbose_name="Место хранения",
    )

    class Meta(WarehouseStorageAssignmentBase.Meta):
        verbose_name = "размещение CD на складе"
        verbose_name_plural = "размещения CD на складах"
        constraints = [
            models.UniqueConstraint(fields=("stock", "location"), name="unique_cd_stock_storage_location"),
            models.UniqueConstraint(fields=("stock", "position"), name="unique_cd_stock_storage_position"),
        ]


class TechWarehouseStorageAssignment(WarehouseStorageAssignmentBase):
    stock = models.ForeignKey(
        TechWarehouseStock, on_delete=models.CASCADE, related_name="storage_assignments",
        verbose_name="Остаток Tech",
    )
    location = models.ForeignKey(
        WarehouseStorageLocation, on_delete=models.PROTECT, related_name="tech_assignments",
        verbose_name="Место хранения",
    )

    class Meta(WarehouseStorageAssignmentBase.Meta):
        verbose_name = "размещение техники на складе"
        verbose_name_plural = "размещения техники на складах"
        constraints = [
            models.UniqueConstraint(fields=("stock", "location"), name="unique_tech_stock_storage_location"),
            models.UniqueConstraint(fields=("stock", "position"), name="unique_tech_stock_storage_position"),
        ]


class WarehouseTransfer(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Создан"
        ASSEMBLED = "assembled", "Собран"
        SHIPPED = "shipped", "Отправлен"
        ACCEPTED = "accepted", "Принят"

    source_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="outgoing_transfers", verbose_name="Склад-отправитель"
    )
    destination_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="incoming_transfers", verbose_name="Склад-получатель"
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.CREATED, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_warehouse_transfers", verbose_name="Создал"
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)
    assembled_at = models.DateTimeField("Собран", null=True, blank=True, editable=False)
    shipped_at = models.DateTimeField("Отправлен", null=True, blank=True, editable=False)
    accepted_at = models.DateTimeField("Принят", null=True, blank=True, editable=False)
    assembled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assembled_warehouse_transfers",
        verbose_name="Собрал", null=True, blank=True, editable=False,
    )
    shipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shipped_warehouse_transfers",
        verbose_name="Отправил", null=True, blank=True, editable=False,
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="accepted_warehouse_transfers", verbose_name="Принял", null=True, blank=True, editable=False,
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "межскладское перемещение"
        verbose_name_plural = "межскладские перемещения"
        permissions = [
            ("view_transfers", "Может просматривать перемещения"),
            ("create_transfer", "Может создавать перемещения"),
            ("mark_transfer_assembled", "Может отмечать перемещение собранным"),
            ("mark_transfer_shipped", "Может отмечать перемещение отправленным"),
            ("mark_transfer_accepted", "Может принимать перемещение"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(source_warehouse=models.F("destination_warehouse")),
                name="warehouse_transfer_different_destinations",
            )
        ]

    @property
    def position_count(self):
        return self.cd_items.count() + self.tech_items.count()

    @property
    def total_units(self):
        return sum(item.quantity for item in self.cd_items.all()) + sum(
            item.quantity for item in self.tech_items.all()
        )

    def __str__(self):
        return f"Перемещение №{self.pk}: {self.source_warehouse} → {self.destination_warehouse}"


class WarehouseTransferItemBase(models.Model):
    quantity = models.PositiveIntegerField("Количество")

    class Meta:
        abstract = True


class CDWarehouseTransferItem(WarehouseTransferItemBase):
    transfer = models.ForeignKey(
        WarehouseTransfer, on_delete=models.PROTECT, related_name="cd_items", verbose_name="Перемещение"
    )
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="warehouse_transfer_items", verbose_name="CD")

    class Meta:
        verbose_name = "позиция CD в перемещении"
        verbose_name_plural = "позиции CD в перемещениях"
        constraints = [
            models.UniqueConstraint(fields=("transfer", "cd"), name="unique_cd_transfer_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="cd_transfer_quantity_positive"),
        ]


class TechWarehouseTransferItem(WarehouseTransferItemBase):
    transfer = models.ForeignKey(
        WarehouseTransfer, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Перемещение"
    )
    tech = models.ForeignKey(
        Tech, on_delete=models.PROTECT, related_name="warehouse_transfer_items", verbose_name="Техника"
    )

    class Meta:
        verbose_name = "позиция техники в перемещении"
        verbose_name_plural = "позиции техники в перемещениях"
        constraints = [
            models.UniqueConstraint(fields=("transfer", "tech"), name="unique_tech_transfer_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="tech_transfer_quantity_positive"),
        ]
