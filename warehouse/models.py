from django.conf import settings
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
        ]

    def __str__(self):
        return self.name


class WarehouseStockBase(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, verbose_name="Склад")
    quantity = models.PositiveIntegerField("Количество", default=0)

    class Meta:
        abstract = True


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
