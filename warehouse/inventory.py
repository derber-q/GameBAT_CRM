"""Канонический физический остаток всех складов для внешних площадок."""
from django.db.models import Sum


def global_stock(product):
    return int(product.warehouse_stocks.aggregate(total=Sum("quantity"))["total"] or 0)
