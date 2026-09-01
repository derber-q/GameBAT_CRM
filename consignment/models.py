from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import SalesPlatform


class ConsignmentStockBase(models.Model):
    platform = models.ForeignKey(SalesPlatform, on_delete=models.PROTECT, verbose_name="Площадка")
    quantity = models.PositiveIntegerField("Количество", default=0)
    reward_per_unit = models.DecimalField(
        "Вознаграждение за единицу", max_digits=16, decimal_places=2,
        default=0, validators=[MinValueValidator(0)],
    )

    class Meta:
        abstract = True

    @property
    def potential_reward(self):
        return self.quantity * self.reward_per_unit


class CDConsignmentStock(ConsignmentStockBase):
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="consignment_stocks", verbose_name="CD")

    class Meta:
        verbose_name = "остаток CD на реализации"
        verbose_name_plural = "остатки CD на реализации"
        permissions = [
            ("transfer_stock", "Может передавать товар на реализацию"),
            ("return_stock", "Может возвращать товар с реализации"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("platform", "cd"), name="unique_cd_platform_stock"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="cd_stock_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(reward_per_unit__gte=0), name="cd_stock_reward_nonnegative"),
        ]

    def __str__(self):
        return f"{self.platform}: {self.cd}"


class TechConsignmentStock(ConsignmentStockBase):
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, related_name="consignment_stocks", verbose_name="Техника")

    class Meta:
        verbose_name = "остаток техники на реализации"
        verbose_name_plural = "остатки техники на реализации"
        constraints = [
            models.UniqueConstraint(fields=("platform", "tech"), name="unique_tech_platform_stock"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="tech_stock_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(reward_per_unit__gte=0), name="tech_stock_reward_nonnegative"),
        ]

    def __str__(self):
        return f"{self.platform}: {self.tech}"
