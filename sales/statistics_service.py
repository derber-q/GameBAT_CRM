"""Единый источник расчётов для страницы, графика и Excel-отчёта."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Prefetch
from django.utils import timezone

from catalog.models import CD, Tech
from catalog.product_search import filter_products_by_text

from .models import Sale, SaleCDItem, SaleTechItem


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
PERCENT = Decimal("0.01")
CHANNEL_LABELS = {
    "retail": "Розница", "wholesale": "Оптовые", "avito": "Avito",
    "yandex_market": "Яндекс Маркет", "consignment": "Реализация",
}
MONTH_NAMES = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


def channel_for_sale(sale):
    if sale.sale_type in (Sale.SaleType.WHOLESALE_PICKUP, Sale.SaleType.WHOLESALE_DELIVERY):
        return "wholesale"
    return sale.sale_type


def percentage(part, total):
    if part is None or total is None or total == 0:
        return None
    return (part * Decimal("100") / total).quantize(PERCENT, rounding=ROUND_HALF_UP)


@dataclass
class LineRow:
    item: object
    kind: str
    product_id: int
    name: str
    sku: str
    category: str
    quantity: int
    unit_price: Decimal
    unit_cost: Decimal | None
    revenue: Decimal
    cost: Decimal | None
    profit: Decimal | None
    margin: Decimal | None
    markup: Decimal | None


@dataclass
class SaleRow:
    sale: Sale
    lines: list[LineRow]
    channel: str
    channel_label: str
    goods_total: Decimal
    overpayment: Decimal
    actual_revenue: Decimal
    cost: Decimal | None
    items_profit: Decimal | None
    profit: Decimal | None
    margin: Decimal | None
    markup: Decimal | None
    units: int
    positions: int
    missing_lines: int


@dataclass
class Aggregate:
    sales_count: int = 0
    units: int = 0
    goods_total: Decimal = ZERO
    overpayment: Decimal = ZERO
    actual_revenue: Decimal = ZERO
    cost: Decimal | None = ZERO
    profit: Decimal | None = ZERO
    margin: Decimal | None = None
    markup: Decimal | None = None
    average_check: Decimal | None = None
    missing_sales: int = 0
    missing_lines: int = 0


@dataclass
class ProductAggregate:
    kind: str
    product_id: int
    name: str
    sku: str
    category: str
    units: int = 0
    sales_ids: set[int] = field(default_factory=set)
    revenue: Decimal = ZERO
    cost: Decimal | None = ZERO
    profit: Decimal | None = ZERO
    margin: Decimal | None = None
    markup: Decimal | None = None
    average_unit_price: Decimal | None = None
    profit_share: Decimal | None = None

    @property
    def sales_count(self):
        return len(self.sales_ids)


@dataclass
class GroupRow:
    key: str
    label: str
    totals: Aggregate


@dataclass
class StatisticsReport:
    filters: dict
    sales: list[SaleRow]
    products: list[ProductAggregate]
    channels: list[GroupRow]
    time_series: list[GroupRow]
    totals: Aggregate
    undated_completed_count: int
    chart: dict


def _matching_sale_ids(filters):
    """Return sale IDs containing a matching item; selected sales retain all lines."""
    query = str(filters.get("product_query") or "").strip()
    cd_fields = ("platform", "game_series")
    tech_fields = ("brand", "product_type")
    if not query and not any(filters.get(name) for name in (*cd_fields, *tech_fields)):
        return None
    cd_queryset = CD.objects.all()
    tech_queryset = Tech.objects.all()
    if query:
        cd_queryset = filter_products_by_text(cd_queryset, query, product_kind="cd")
        tech_queryset = filter_products_by_text(tech_queryset, query, product_kind="tech")
    if filters.get("platform"):
        cd_queryset = cd_queryset.filter(platform=filters["platform"])
    if filters.get("game_series"):
        cd_queryset = cd_queryset.filter(game_series=filters["game_series"])
    if filters.get("brand"):
        tech_queryset = tech_queryset.filter(brand=filters["brand"])
    if filters.get("product_type"):
        tech_queryset = tech_queryset.filter(product_type=filters["product_type"])
    cd_restricted = any(filters.get(name) for name in cd_fields)
    tech_restricted = any(filters.get(name) for name in tech_fields)
    ids = set()
    if not tech_restricted or cd_restricted:
        ids.update(SaleCDItem.objects.filter(cd__in=cd_queryset).values_list("sale_id", flat=True))
    if not cd_restricted or tech_restricted:
        ids.update(SaleTechItem.objects.filter(tech__in=tech_queryset).values_list("sale_id", flat=True))
    return ids


def _base_queryset(filters):
    queryset = Sale.objects.filter(
        order_status=Sale.OrderStatus.DELIVERED,
        payment_status=Sale.PaymentStatus.PAID,
        cancelled_at__isnull=True,
        completed_at__isnull=False,
    )
    if filters.get("date_from"):
        queryset = queryset.filter(completed_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(completed_at__date__lte=filters["date_to"])
    if filters.get("sale_ids"):
        queryset = queryset.filter(pk__in=filters["sale_ids"])
    if filters.get("warehouse"):
        queryset = queryset.filter(warehouse=filters["warehouse"])
    if filters.get("payment_methods"):
        queryset = queryset.filter(payment_method__in=filters["payment_methods"])
    if filters.get("channels"):
        sale_types = []
        for channel in filters["channels"]:
            if channel == "wholesale":
                sale_types.extend((Sale.SaleType.WHOLESALE_PICKUP, Sale.SaleType.WHOLESALE_DELIVERY))
            else:
                sale_types.append(channel)
        queryset = queryset.filter(sale_type__in=sale_types)
    matching_ids = _matching_sale_ids(filters)
    if matching_ids is not None:
        queryset = queryset.filter(pk__in=matching_ids)
    return queryset.select_related("warehouse", "consignment_platform").prefetch_related(
        Prefetch("cd_items", queryset=SaleCDItem.objects.select_related("cd__platform", "cd__game_series")),
        Prefetch("tech_items", queryset=SaleTechItem.objects.select_related("tech__brand", "tech__product_type")),
    ).order_by("completed_at", "pk")


def _line(item, kind):
    product = item.cd if kind == "cd" else item.tech
    category = (
        product.platform.name if kind == "cd" and product.platform_id else
        product.product_type.name if kind == "tech" and product.product_type_id else "—"
    )
    revenue = (item.unit_price * item.quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    unit_cost = item.unit_cost_snapshot
    cost = (unit_cost * item.quantity).quantize(CENT, rounding=ROUND_HALF_UP) if unit_cost is not None else None
    profit = revenue - cost if cost is not None else None
    return LineRow(
        item=item, kind=kind, product_id=product.pk,
        name=item.product_name_snapshot, sku=item.article_snapshot, category=category,
        quantity=item.quantity, unit_price=item.unit_price, unit_cost=unit_cost,
        revenue=revenue, cost=cost, profit=profit,
        margin=percentage(profit, revenue), markup=percentage(profit, cost),
    )


def _sale_row(sale):
    lines = [_line(item, "cd") for item in sale.cd_items.all()]
    lines.extend(_line(item, "tech") for item in sale.tech_items.all())
    missing = sum(line.cost is None for line in lines)
    cost = sum((line.cost for line in lines), ZERO) if not missing else None
    items_profit = sum((line.profit for line in lines), ZERO) if not missing else None
    goods_total = sale.total_amount
    overpayment = sale.extra_cash_amount
    actual = goods_total + overpayment
    profit = items_profit + overpayment if items_profit is not None else None
    channel = channel_for_sale(sale)
    return SaleRow(
        sale=sale, lines=lines, channel=channel,
        channel_label=CHANNEL_LABELS.get(channel, sale.get_sale_type_display()),
        goods_total=goods_total, overpayment=overpayment, actual_revenue=actual,
        cost=cost, items_profit=items_profit, profit=profit,
        margin=percentage(profit, actual), markup=percentage(profit, cost),
        units=sum(line.quantity for line in lines), positions=len(lines), missing_lines=missing,
    )


def _aggregate(rows):
    rows = list(rows)
    result = Aggregate(
        sales_count=len(rows), units=sum(row.units for row in rows),
        goods_total=sum((row.goods_total for row in rows), ZERO),
        overpayment=sum((row.overpayment for row in rows), ZERO),
        actual_revenue=sum((row.actual_revenue for row in rows), ZERO),
        missing_sales=sum(row.cost is None for row in rows),
        missing_lines=sum(row.missing_lines for row in rows),
    )
    if result.missing_sales:
        result.cost = None
        result.profit = None
    else:
        result.cost = sum((row.cost for row in rows), ZERO)
        result.profit = sum((row.profit for row in rows), ZERO)
    result.margin = percentage(result.profit, result.actual_revenue)
    result.markup = percentage(result.profit, result.cost)
    result.average_check = (
        (result.actual_revenue / result.sales_count).quantize(CENT, rounding=ROUND_HALF_UP)
        if result.sales_count else None
    )
    return result


def _product_rows(rows):
    groups = {}
    for row in rows:
        for line in row.lines:
            key = (line.kind, line.product_id)
            if key not in groups:
                groups[key] = ProductAggregate(
                    kind=line.kind, product_id=line.product_id, name=line.name,
                    sku=line.sku, category=line.category,
                )
            group = groups[key]
            group.units += line.quantity
            group.sales_ids.add(row.sale.pk)
            group.revenue += line.revenue
            if line.cost is None:
                group.cost = None
                group.profit = None
            elif group.cost is not None:
                group.cost += line.cost
                group.profit += line.profit
    result = list(groups.values())
    total_items_profit = (
        sum((group.profit for group in result), ZERO)
        if all(group.profit is not None for group in result) else None
    )
    for group in result:
        group.margin = percentage(group.profit, group.revenue)
        group.markup = percentage(group.profit, group.cost)
        group.average_unit_price = (group.revenue / group.units).quantize(CENT, rounding=ROUND_HALF_UP)
        group.profit_share = percentage(group.profit, total_items_profit)
    return result


def _time_key(sale, grouping):
    day = timezone.localtime(sale.completed_at).date()
    if grouping == "week":
        start = day - timedelta(days=day.weekday())
        return start, f"{start:%d.%m.%Y}–{start + timedelta(days=6):%d.%m.%Y}"
    if grouping == "month":
        start = day.replace(day=1)
        return start, f"{MONTH_NAMES[start.month - 1]} {start.year}"
    return day, day.strftime("%d.%m.%Y")


def _group_rows(rows, grouping):
    channels = defaultdict(list)
    times = defaultdict(list)
    labels = {}
    for row in rows:
        channels[row.channel].append(row)
        key, label = _time_key(row.sale, grouping)
        times[key].append(row)
        labels[key] = label
    channel_rows = [GroupRow(key, CHANNEL_LABELS.get(key, key), _aggregate(values))
                    for key, values in channels.items()]
    channel_rows.sort(key=lambda row: list(CHANNEL_LABELS).index(row.key)
                      if row.key in CHANNEL_LABELS else len(CHANNEL_LABELS))
    time_rows = [GroupRow(str(key), labels[key], _aggregate(times[key])) for key in sorted(times)]
    return channel_rows, time_rows


def _sort_with_missing(rows, key, descending):
    known = [row for row in rows if key(row) is not None]
    missing = [row for row in rows if key(row) is None]
    return sorted(known, key=key, reverse=descending) + missing


def _sort_sales(rows, choice):
    keys = {
        "date": lambda row: row.sale.completed_at,
        "revenue": lambda row: row.actual_revenue,
        "cost": lambda row: row.cost,
        "profit": lambda row: row.profit,
        "margin": lambda row: row.margin,
        "units": lambda row: row.units,
    }
    return _sort_with_missing(rows, keys.get(choice.lstrip("-"), keys["date"]), choice.startswith("-"))


def _sort_products(rows, choice):
    keys = {
        "units": lambda row: row.units, "profit": lambda row: row.profit,
        "revenue": lambda row: row.revenue, "sales": lambda row: row.sales_count,
    }
    return _sort_with_missing(rows, keys.get(choice.lstrip("-"), keys["units"]), choice.startswith("-"))


def _chart_data(time_rows):
    if not time_rows:
        return {"series": [], "labels": []}
    values = [value for row in time_rows for value in
              (row.totals.actual_revenue, row.totals.cost, row.totals.profit) if value is not None]
    lower, upper = min(ZERO, *values), max(ZERO, *values)
    if lower == upper:
        upper += Decimal("1")
    width = 900
    height = 230
    def point(index, value):
        x = 32 + (index * (width - 64) / max(len(time_rows) - 1, 1))
        y = 12 + float((upper - value) / (upper - lower)) * (height - 38)
        return f"{x:.1f},{y:.1f}"
    series = []
    for label, attribute, color in (
        ("Выручка", "actual_revenue", "#287f98"),
        ("Себестоимость", "cost", "#8999a8"),
        ("Чистая прибыль", "profit", "#319b67"),
    ):
        segments, current, points = [], [], []
        for index, row in enumerate(time_rows):
            value = getattr(row.totals, attribute)
            if value is None:
                if current:
                    segments.append(" ".join(current))
                    current = []
            else:
                coordinates = point(index, value)
                current.append(coordinates)
                points.append(coordinates.split(","))
        if current:
            segments.append(" ".join(current))
        series.append({"label": label, "color": color, "segments": segments, "points": points})
    label_step = max(1, (len(time_rows) + 7) // 8)
    x_labels = [{"x": f"{32 + (index * (width - 64) / max(len(time_rows) - 1, 1)):.1f}",
                 "label": row.label} for index, row in enumerate(time_rows)
                if index % label_step == 0 or index == len(time_rows) - 1]
    return {"series": series, "labels": x_labels,
            "zero_y": float((upper / (upper - lower)) * (height - 38)) + 12,
            "width": width, "height": height}


def build_sales_statistics_report(filters):
    """Builds all surfaces from one completed-sale selection and immutable item snapshots."""
    undated = Sale.objects.filter(
        order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.PAID,
        cancelled_at__isnull=True, completed_at__isnull=True,
    ).count()
    sales = [_sale_row(sale) for sale in _base_queryset(filters)]
    minimum, maximum = filters.get("min_profit"), filters.get("max_profit")
    if minimum is not None or maximum is not None:
        sales = [row for row in sales if row.profit is not None
                 and (minimum is None or row.profit >= minimum)
                 and (maximum is None or row.profit <= maximum)]
    totals = _aggregate(sales)
    products = _sort_products(_product_rows(sales), filters.get("product_sort") or "-units")
    channels, time_series = _group_rows(sales, filters.get("grouping") or "day")
    return StatisticsReport(
        filters=filters, sales=_sort_sales(sales, filters.get("sale_sort") or "-date"),
        products=products, channels=channels, time_series=time_series, totals=totals,
        undated_completed_count=undated, chart=_chart_data(time_series),
    )
