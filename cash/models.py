from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from warehouse.models import Warehouse


class CashRegister(models.Model):
    warehouse = models.OneToOneField(
        Warehouse, on_delete=models.PROTECT, related_name="cash_register", verbose_name="Склад"
    )
    balance = models.DecimalField(
        "Остаток наличных", max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = "касса"
        verbose_name_plural = "кассы"
        permissions = [
            ("view_cash_register", "Может просматривать остаток кассы"),
            ("view_cash_history", "Может просматривать историю кассы"),
            ("deposit_cash", "Может вносить наличные"),
            ("collect_cash", "Может инкассировать наличные"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(balance__gte=0), name="cash_register_balance_nonnegative")
        ]

    def __str__(self):
        return f"Касса: {self.warehouse}"


class CashTransaction(models.Model):
    class OperationType(models.TextChoices):
        DEPOSIT = "deposit", "Внесение наличных"
        COLLECTION = "collection", "Инкассация"
        SALE_PAYMENT = "sale_payment", "Оплата продажи"

    cash_register = models.ForeignKey(
        CashRegister, on_delete=models.PROTECT, related_name="transactions", verbose_name="Касса"
    )
    operation_type = models.CharField("Операция", max_length=24, choices=OperationType.choices)
    amount = models.DecimalField(
        "Сумма", max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    comment = models.TextField("Комментарий")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_transactions", verbose_name="Провёл"
    )
    created_at = models.DateTimeField("Проведена", auto_now_add=True)
    sale = models.OneToOneField(
        "sales.Sale", on_delete=models.PROTECT, related_name="cash_transaction",
        verbose_name="Продажа", null=True, blank=True,
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "кассовая операция"
        verbose_name_plural = "кассовые операции"
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="cash_transaction_amount_positive")
        ]

    @property
    def signed_amount(self):
        return -self.amount if self.operation_type == self.OperationType.COLLECTION else self.amount

    def __str__(self):
        return f"{self.get_operation_type_display()}: {self.amount}"
