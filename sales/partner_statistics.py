"""Единая лента продаж и движений долга для HTML и Excel; выручка считается прежним сервисом."""
from dataclasses import dataclass
from decimal import Decimal
from creditors.models import CreditorTransaction

ZERO = Decimal('0.00')


@dataclass
class FinancialOperation:
    date: object
    kind: str
    partner_name: str
    sale: object
    amount: Decimal
    actual_money: Decimal = ZERO
    repayment: Decimal = ZERO
    offset: Decimal = ZERO
    debt_change: Decimal = ZERO
    old_debt: Decimal | None = None
    new_debt: Decimal | None = None
    comment: str = ''
    order_id: int | None = None


def financial_operations(filters, sales):
    operations = []
    for row in sales:
        sale = row.sale
        actual = sale.cash_received_amount if sale.cash_received_amount is not None else sale.total_amount
        actual -= sale.procurement_prepaid_amount
        operations.append(FinancialOperation(sale.completed_at, sale.get_operation_kind_display(),
            sale.partner_name_snapshot, sale, row.goods_total, actual_money=actual, comment=sale.note))
    query = CreditorTransaction.objects.select_related('creditor__partner', 'sale', 'warehouse', 'reversal_of')
    for key, lookup in (('date_from', 'created_at__date__gte'), ('date_to', 'created_at__date__lte'),
                        ('warehouse', 'warehouse'), ('partner', 'creditor__partner')):
        if filters.get(key):
            query = query.filter(**{lookup: filters[key]})
    if filters.get('arbitrary_partner_name'):
        query = query.none()
    if filters.get('sale_ids'):
        query = query.filter(sale_id__in=filters['sale_ids'])
    if filters.get('channels'):
        query = query.filter(sale__sale_type__in=filters['channels'])
    if filters.get('payment_methods'):
        methods = filters['payment_methods']
        sources = []
        if any(method in methods for method in ('cash', 'cash_postpay')): sources.append('cash')
        if any(method in methods for method in ('bank_account', 'bank_transfer_postpay')): sources.append('bank')
        from django.db.models import Q
        query = query.filter(Q(sale__payment_method__in=methods) | Q(sale__isnull=True, money_source_type__in=sources))
    if filters.get('operation_kind'):
        query = query.filter(sale__operation_kind=filters['operation_kind'])
    if any(filters.get(key) not in (None, '') for key in ('product_query', 'platform', 'game_series', 'brand', 'product_type', 'min_profit', 'max_profit')):
        query = query.filter(sale_id__in=[row.sale.pk for row in sales])
    for entry in query.order_by('created_at', 'pk'):
        partner = getattr(entry.creditor, 'partner', None)
        name = entry.partner_name_snapshot or (partner.name if partner else entry.creditor.name)
        cash = -entry.delta if not entry.sale_id and entry.money_source_type != 'offset' else ZERO
        reversal_sign = -1 if entry.kind == CreditorTransaction.Kind.REVERSAL else 1
        original_kind = entry.reversal_of.kind if entry.reversal_of_id else entry.kind
        repayment = entry.amount * reversal_sign if original_kind == CreditorTransaction.Kind.REPAYMENT else ZERO
        offset = entry.amount * reversal_sign if original_kind == CreditorTransaction.Kind.OFFSET else ZERO
        if original_kind == CreditorTransaction.Kind.SALE_DEBT and entry.sale_id:
            offset = entry.sale.debt_offset_amount * reversal_sign
        # Самостоятельное уменьшение положительного долга также является погашением.
        if not entry.sale_id and entry.delta < 0 and entry.old_debt > 0:
            repayment = min(entry.old_debt, -entry.delta)
        operations.append(FinancialOperation(entry.created_at, entry.get_kind_display(), name, entry.sale,
            entry.amount, cash, repayment, offset, entry.delta, entry.old_debt, entry.new_debt, entry.comment))
    # Приходящие деньги импортных заказов показываются без выдуманной продажи и прибыли.
    if not any(filters.get(key) for key in ('channels', 'operation_kind', 'sale_ids', 'product_query', 'platform', 'game_series', 'brand', 'product_type')) and all(filters.get(key) is None for key in ('min_profit', 'max_profit')):
        from cash.models import CashTransaction
        cash_entries = CashTransaction.objects.filter(customer_order__isnull=False).select_related('customer_order')
        for key, lookup in (('date_from', 'created_at__date__gte'), ('date_to', 'created_at__date__lte'),
                ('warehouse', 'cash_register__warehouse'), ('partner', 'customer_order__partner')):
            if filters.get(key): cash_entries = cash_entries.filter(**{lookup: filters[key]})
        if filters.get('arbitrary_partner_name'):
            cash_entries = cash_entries.filter(customer_order__partner__isnull=True,
                customer_order__partner_name_snapshot=filters['arbitrary_partner_name'])
        if filters.get('payment_methods') and not any(method in filters['payment_methods'] for method in ('cash', 'cash_postpay')):
            cash_entries = cash_entries.none()
        for entry in cash_entries:
            order = entry.customer_order
            operations.append(FinancialOperation(entry.created_at, f'{entry.get_operation_type_display()} · заказ №{order.pk}',
                order.partner_name_snapshot or order.recipient, None, entry.amount, entry.signed_amount,
                comment=entry.comment, order_id=order.pk))
    return sorted(operations, key=lambda row: row.date, reverse=True)
