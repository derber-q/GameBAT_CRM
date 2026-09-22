from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.decorators import permission_required_all, permission_required_any

from .statistics_excel import render_statistics_workbook
from .statistics_forms import SaleStatisticsFilterForm
from .statistics_service import build_sales_statistics_report


def _filter_form(request):
    data = request.GET.copy()
    for key, default in (("grouping", "day"), ("sale_sort", "-date"), ("product_sort", "-units")):
        if not data.get(key):
            data[key] = default
    return SaleStatisticsFilterForm(data)


def _report(request):
    form = _filter_form(request)
    return form, build_sales_statistics_report(form.cleaned_data) if form.is_valid() else None


@permission_required_any("sales.view_sales_statistics")
def statistics_index(request):
    form, report = _report(request)
    sale_page = Paginator(report.sales, 25).get_page(request.GET.get("page")) if report else None
    product_page = Paginator(report.products, 25).get_page(request.GET.get("product_page")) if report else None
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("product_page", None)
    return render(request, "sales/statistics.html", {
        "form": form, "report": report, "sale_page": sale_page, "product_page": product_page,
        "filter_query": params.urlencode(), "today": timezone.localdate().isoformat(),
        "can_export": request.user.is_superuser or request.user.has_perm("sales.export_sales_statistics"),
        "can_view_sale_detail": request.user.is_superuser or request.user.has_perm("sales.view_sale_detail"),
        "advanced_active": bool(report and any(report.filters.get(key) for key in (
            "product_query", "platform", "game_series", "brand", "product_type", "sale_ids",
            "min_profit", "max_profit",
        ))),
    })


@permission_required_all("sales.view_sales_statistics", "sales.export_sales_statistics")
def statistics_export(request):
    form, report = _report(request)
    if report is None:
        return HttpResponse("Некорректные фильтры отчёта.", status=400)
    payload = render_statistics_workbook(report)
    response = HttpResponse(
        payload, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="sales_statistics.xlsx"'
    return response
