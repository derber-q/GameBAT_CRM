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


class Safe(models.Model):
    warehouse = models.OneToOneField(
        Warehouse, on_delete=models.PROTECT, related_name="safe", verbose_name="Склад"
    )
    balance = models.DecimalField(
        "Остаток наличных", max_digits=20, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "сейф"
        verbose_name_plural = "сейфы"
        permissions = [
            ("deposit_safe", "Может вносить наличные в сейф"),
            ("collect_safe", "Может инкассировать наличные из сейфа"),
            ("transfer_cash_to_safe", "Может переводить наличные из кассы в сейф"),
            ("transfer_safe_to_cash", "Может переводить наличные из сейфа в кассу"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(balance__gte=0), name="safe_balance_nonnegative")
        ]

    def __str__(self):
        return f"Сейф: {self.warehouse}"


class CashTransaction(models.Model):
    class OperationType(models.TextChoices):
        DEPOSIT = "deposit", "Внесение наличных"
        COLLECTION = "collection", "Инкассация"
        SALE_PAYMENT = "sale_payment", "Оплата продажи"
        SALE_REFUND = "sale_refund", "Возврат по отменённой продаже"
        SAFE_DEPOSIT = "safe_deposit", "Внесение в сейф"
        SAFE_COLLECTION = "safe_collection", "Инкассация из сейфа"
        CASH_TO_SAFE = "cash_to_safe", "Перевод: касса → сейф"
        SAFE_TO_CASH = "safe_to_cash", "Перевод: сейф → касса"
        CUSTOMER_ORDER_PREPAYMENT = "order_prepayment", "Предоплата закупочного заказа"
        CUSTOMER_ORDER_REFUND = "order_refund", "Возврат по закупочному заказу"
        CUSTOMER_ORDER_POSTPAYMENT = "order_postpayment", "Постоплата закупочного заказа"

    cash_register = models.ForeignKey(
        CashRegister, on_delete=models.PROTECT, related_name="transactions", verbose_name="Касса"
    )
    safe = models.ForeignKey(
        Safe, on_delete=models.PROTECT, related_name="transactions", verbose_name="Сейф",
        null=True, blank=True, editable=False,
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
    sale = models.ForeignKey(
        "sales.Sale", on_delete=models.PROTECT, related_name="cash_transactions",
        verbose_name="Продажа", null=True, blank=True, editable=False,
    )
    operation_key = models.UUIDField(
        "Ключ операции", null=True, blank=True, unique=True, editable=False,
    )
    customer_order = models.ForeignKey(
        "orders.CustomerProcurementOrder", on_delete=models.PROTECT,
        related_name="cash_transactions", verbose_name="Закупочный заказ",
        null=True, blank=True, editable=False,
    )
    order_adjustment = models.OneToOneField(
        "orders.OrderAdjustment", on_delete=models.PROTECT,
        related_name="refund_transaction", verbose_name="Корректировка заказа",
        null=True, blank=True, editable=False,
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "кассовая операция"
        verbose_name_plural = "кассовые операции"
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="cash_transaction_amount_positive"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        operation_type__in=("deposit", "collection", "sale_payment", "sale_refund"),
                        safe__isnull=True,
                    )
                    | models.Q(
                        operation_type__in=(
                            "safe_deposit", "safe_collection", "cash_to_safe", "safe_to_cash",
                        ),
                        safe__isnull=False,
                    )
                    | models.Q(
                        operation_type__in=("order_prepayment", "order_refund", "order_postpayment"),
                        safe__isnull=True,
                        customer_order__isnull=False,
                    )
                ),
                name="cash_transaction_safe_matches_type",
            ),
            models.UniqueConstraint(
                fields=("customer_order",), condition=models.Q(operation_type="order_prepayment"),
                name="unique_customer_order_prepayment",
            ),
            models.UniqueConstraint(
                fields=("customer_order",), condition=models.Q(operation_type="order_postpayment"),
                name="unique_customer_order_postpayment",
            ),
            models.UniqueConstraint(
                fields=("sale", "operation_type"),
                condition=models.Q(
                    sale__isnull=False,
                    operation_type__in=("sale_payment", "sale_refund"),
                ),
                name="unique_sale_cash_operation_type",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        operation_type__in=("sale_payment", "sale_refund"), sale__isnull=False,
                    )
                    | (
                        ~models.Q(operation_type__in=("sale_payment", "sale_refund"))
                        & models.Q(sale__isnull=True)
                    )
                ),
                name="sale_cash_operation_has_sale",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(operation_type="order_refund", order_adjustment__isnull=False)
                    | (~models.Q(operation_type="order_refund") & models.Q(order_adjustment__isnull=True))
                ),
                name="order_refund_has_adjustment",
            ),
        ]

    @property
    def signed_amount(self):
        return -self.amount if self.operation_type in {
            self.OperationType.COLLECTION,
            self.OperationType.SALE_REFUND,
            self.OperationType.SAFE_COLLECTION,
            self.OperationType.CUSTOMER_ORDER_REFUND,
        } else self.amount

    @property
    def is_internal_transfer(self):
        return self.operation_type in {
            self.OperationType.CASH_TO_SAFE,
            self.OperationType.SAFE_TO_CASH,
        }

    @property
    def is_outflow(self):
        return self.operation_type in {
            self.OperationType.COLLECTION,
            self.OperationType.SALE_REFUND,
            self.OperationType.SAFE_COLLECTION,
            self.OperationType.CUSTOMER_ORDER_REFUND,
        }

    @property
    def source_label(self):
        return {
            self.OperationType.DEPOSIT: "Внешнее поступление",
            self.OperationType.COLLECTION: "Касса",
            self.OperationType.SALE_PAYMENT: "Продажа",
            self.OperationType.SALE_REFUND: "Касса",
            self.OperationType.SAFE_DEPOSIT: "Внешнее поступление",
            self.OperationType.SAFE_COLLECTION: "Сейф",
            self.OperationType.CASH_TO_SAFE: "Касса",
            self.OperationType.SAFE_TO_CASH: "Сейф",
            self.OperationType.CUSTOMER_ORDER_PREPAYMENT: "Клиент",
            self.OperationType.CUSTOMER_ORDER_REFUND: "Касса",
            self.OperationType.CUSTOMER_ORDER_POSTPAYMENT: "Клиент",
        }[self.operation_type]

    @property
    def destination_label(self):
        return {
            self.OperationType.DEPOSIT: "Касса",
            self.OperationType.COLLECTION: "Инкассация",
            self.OperationType.SALE_PAYMENT: "Касса",
            self.OperationType.SALE_REFUND: "Клиент",
            self.OperationType.SAFE_DEPOSIT: "Сейф",
            self.OperationType.SAFE_COLLECTION: "Инкассация",
            self.OperationType.CASH_TO_SAFE: "Сейф",
            self.OperationType.SAFE_TO_CASH: "Касса",
            self.OperationType.CUSTOMER_ORDER_PREPAYMENT: "Касса",
            self.OperationType.CUSTOMER_ORDER_REFUND: "Клиент",
            self.OperationType.CUSTOMER_ORDER_POSTPAYMENT: "Касса",
        }[self.operation_type]

    def __str__(self):
        return f"{self.get_operation_type_display()}: {self.amount}"
