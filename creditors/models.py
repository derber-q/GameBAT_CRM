from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from cash.models import CashTransaction
from warehouse.models import Warehouse


class Creditor(models.Model):
    name = models.CharField("Название", max_length=255, unique=True)
    current_debt = models.DecimalField(
        "Текущая задолженность", max_digits=20, decimal_places=2, default=0,
        validators=[MinValueValidator(0)], editable=False,
    )
    description = models.TextField("Описание", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "кредитор"
        verbose_name_plural = "кредиторы"
        permissions = [
            ("view_creditors", "Может просматривать кредиторов"),
            ("change_debt", "Может изменять задолженность кредиторов"),
            ("view_history", "Может просматривать историю кредиторов"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(current_debt__gte=0), name="creditor_debt_nonnegative"),
        ]

    def __str__(self):
        return self.name


class CreditorTransaction(models.Model):
    class MoneySourceType(models.TextChoices):
        CASH = "cash", "Касса"
        SAFE = "safe", "Сейф"

    creditor = models.ForeignKey(
        Creditor, on_delete=models.PROTECT, related_name="transactions", verbose_name="Кредитор",
    )
    old_debt = models.DecimalField("Задолженность до", max_digits=20, decimal_places=2)
    new_debt = models.DecimalField("Задолженность после", max_digits=20, decimal_places=2)
    delta = models.DecimalField("Изменение задолженности", max_digits=20, decimal_places=2)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="creditor_transactions", verbose_name="Склад",
    )
    money_source_type = models.CharField(
        "Денежное хранилище", max_length=8, choices=MoneySourceType.choices,
    )
    amount = models.DecimalField(
        "Сумма операции", max_digits=20, decimal_places=2, validators=[MinValueValidator(0.01)],
    )
    cash_transaction = models.OneToOneField(
        CashTransaction, on_delete=models.PROTECT, related_name="creditor_transaction",
        verbose_name="Запись денежного журнала", editable=False,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="creditor_transactions", verbose_name="Провёл",
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Проведена", auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "операция кредитора"
        verbose_name_plural = "операции кредиторов"
        constraints = [
            models.CheckConstraint(condition=models.Q(old_debt__gte=0), name="creditor_tx_old_debt_nonnegative"),
            models.CheckConstraint(condition=models.Q(new_debt__gte=0), name="creditor_tx_new_debt_nonnegative"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="creditor_tx_amount_positive"),
            models.CheckConstraint(condition=~models.Q(delta=0), name="creditor_tx_delta_nonzero"),
        ]

    def __str__(self):
        return f"{self.creditor}: {self.old_debt} → {self.new_debt}"
