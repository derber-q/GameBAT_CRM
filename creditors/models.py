from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from cash.models import CashTransaction
from warehouse.models import Warehouse


class Creditor(models.Model):
    name = models.CharField("Название", max_length=255, unique=True)
    current_debt = models.DecimalField(
        "Текущая задолженность", max_digits=20, decimal_places=2, default=0,
        editable=False,
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

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        partner = getattr(self, 'partner', None)
        return partner.name if partner else self.name

    @property
    def debt_direction(self):
        return "Контрагент должен GameBAT" if self.current_debt > 0 else "GameBAT должен контрагенту" if self.current_debt < 0 else "Нет задолженности"

    @property
    def debt_amount(self):
        return abs(self.current_debt)


class CreditorTransaction(models.Model):
    class MoneySourceType(models.TextChoices):
        CASH = "cash", "Касса"
        SAFE = "safe", "Сейф"
        BANK = "bank", "Банковский перевод"
        OFFSET = "offset", "Без движения денег"

    class Kind(models.TextChoices):
        ADJUSTMENT = "adjustment", "Изменение задолженности"
        REPAYMENT = "repayment", "Погашение долга партнёра"
        OFFSET = "offset", "Взаимозачёт долга GameBAT"
        SALE_DEBT = "sale_debt", "Продажа партнёру в долг"
        REVERSAL = "reversal", "Отмена расчёта по продаже"

    kind = models.CharField("Тип операции", max_length=20, choices=Kind.choices, default=Kind.ADJUSTMENT, db_default=Kind.ADJUSTMENT)
    partner_name_snapshot = models.CharField("Партнёр на момент операции", max_length=255, blank=True, db_default='')
    sale = models.ForeignKey("sales.Sale", on_delete=models.PROTECT, null=True, blank=True, related_name="creditor_movements")
    operation_key = models.CharField(max_length=80, unique=True, null=True, blank=True, editable=False)
    reversal_of = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal")

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
        verbose_name="Запись денежного журнала", editable=False, null=True, blank=True,
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
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="creditor_tx_amount_positive"),
            models.CheckConstraint(condition=~models.Q(delta=0), name="creditor_tx_delta_nonzero"),
            models.CheckConstraint(condition=models.Q(delta=models.F('new_debt') - models.F('old_debt')), name='creditor_tx_delta_matches_balances'),
            models.CheckConstraint(condition=models.Q(delta=models.F('amount')) | models.Q(delta=-models.F('amount')), name='creditor_tx_amount_matches_delta'),
            models.CheckConstraint(condition=models.Q(money_source_type__in=('bank', 'offset'), cash_transaction__isnull=True)
                | models.Q(money_source_type__in=('cash', 'safe'), cash_transaction__isnull=False), name='creditor_tx_money_source_consistent'),
        ]

    def __str__(self):
        return f"{self.creditor}: {self.old_debt} → {self.new_debt}"
