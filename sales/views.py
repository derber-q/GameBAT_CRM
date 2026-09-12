from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import permission_required_all, permission_required_any
from price.excel import import_wholesale_price_to_sale
from .forms import SaleCreateForm, WholesalePriceImportForm
from .models import Sale
from .services import advance_order_status, cancel_sale, create_sale, edit_postpay_sale_items, mark_sale_paid


WHOLESALE_DRAFT_SESSION_KEY = "sale_wholesale_import_draft"


def _sale_destination(request, sale):
    if request.user.is_superuser or request.user.has_perm("sales.view_sale_detail"):
        return redirect("sales:detail", pk=sale.pk)
    if request.user.has_perm("sales.view_sales"):
        return redirect("sales:list")
    return redirect("core:home")


def _parse_lines(post):
    types = post.getlist("product_type")
    ids = post.getlist("product_id")
    quantities = post.getlist("quantity")
    if not (len(types) == len(ids) == len(quantities)):
        raise ValidationError("Заполните все поля товарных позиций.")
    return [
        {"product_type": types[index], "product_id": ids[index], "quantity": quantities[index]}
        for index in range(len(types))
    ]


@permission_required_any("sales.view_sales")
def sale_list(request):
    queryset = Sale.objects.select_related(
        "warehouse", "created_by", "consignment_platform"
    ).prefetch_related("cd_items", "tech_items")
    completed = queryset.filter(
        order_status=Sale.OrderStatus.DELIVERED,
        payment_status=Sale.PaymentStatus.PAID,
        cancelled_at__isnull=True,
    ) if (request.user.is_superuser or request.user.has_perm("sales.view_completed_sales")) else []
    incomplete = queryset.filter(cancelled_at__isnull=True).exclude(
        order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.PAID
    )
    cancelled = queryset.filter(cancelled_at__isnull=False)
    return render(request, "sales/list.html", {
        "incomplete_sales": incomplete,
        "completed_sales": completed,
        "cancelled_sales": cancelled,
        "can_view_completed": request.user.is_superuser or request.user.has_perm("sales.view_completed_sales"),
    })


@permission_required_any("sales.create_sale")
def sale_create(request):
    draft = request.session.get(WHOLESALE_DRAFT_SESSION_KEY)
    initial = {}
    if draft:
        initial = {
            "warehouse": draft["warehouse_id"],
            "price_type": Sale.PriceType.WHOLESALE,
            "sale_type": Sale.SaleType.WHOLESALE_PICKUP,
        }
    form = SaleCreateForm(
        request.POST or None, initial=initial, imported_wholesale=bool(draft)
    )
    if request.method == "POST" and form.is_valid():
        try:
            sale = create_sale(
                actor=request.user,
                warehouse_id=form.cleaned_data["warehouse"].pk,
                price_type=form.cleaned_data["price_type"],
                sale_type=form.cleaned_data["sale_type"],
                payment_method=form.cleaned_data["payment_method"],
                lines=_parse_lines(request.POST),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            request.session.pop(WHOLESALE_DRAFT_SESSION_KEY, None)
            messages.success(request, f"Продажа {sale.visible_id} создана.")
            return _sale_destination(request, sale)
    return render(request, "sales/create.html", {
        "form": form,
        "can_view_sales": request.user.is_superuser or request.user.has_perm("sales.view_sales"),
        "can_import_wholesale": request.user.is_superuser or request.user.has_perm("sales.import_wholesale_price"),
        "initial_items": draft["lines"] if draft else [],
        "imported_wholesale": bool(draft),
    })


@permission_required_all("sales.create_sale", "sales.import_wholesale_price")
def sale_wholesale_import(request):
    form = WholesalePriceImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            warehouse, lines = import_wholesale_price_to_sale(form.cleaned_data["file"])
        except ValidationError as exc:
            form.add_error("file", exc)
        else:
            request.session[WHOLESALE_DRAFT_SESSION_KEY] = {
                "warehouse_id": warehouse.pk,
                "lines": lines,
            }
            messages.success(request, "Оптовый прайс проверен. Проверьте обычную форму продажи.")
            return redirect("sales:create")
    return render(request, "sales/import_wholesale.html", {"form": form})


@permission_required_any("sales.view_sale_detail")
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related(
            "warehouse", "created_by", "consignment_platform"
        ).prefetch_related("cd_items__cd", "tech_items__tech"),
        pk=pk,
    )
    rows = [
        {"type": "CD", "name": item.product_name_snapshot, "sku": item.article_snapshot,
         "quantity": item.quantity, "unit_price": item.unit_price, "line_total": item.line_total}
        for item in sale.cd_items.all()
    ] + [
        {"type": "Tech", "name": item.product_name_snapshot, "sku": item.article_snapshot,
         "quantity": item.quantity, "unit_price": item.unit_price, "line_total": item.line_total}
        for item in sale.tech_items.all()
    ]
    next_status = {
        Sale.OrderStatus.CREATED: (Sale.OrderStatus.ASSEMBLED, "Отметить как собранный"),
        Sale.OrderStatus.ASSEMBLED: (Sale.OrderStatus.SHIPPED, "Отметить как отправленный"),
        Sale.OrderStatus.SHIPPED: (Sale.OrderStatus.DELIVERED, "Отметить как доставленный"),
    }.get(sale.order_status)
    if sale.is_cancelled or not (request.user.is_superuser or request.user.has_perm("sales.advance_order_status")):
        next_status = None
    cash_transactions = []
    if request.user.is_superuser or request.user.has_perm("cash.view_cash_history"):
        cash_transactions = sale.cash_transactions.all()
    return render(request, "sales/detail.html", {
        "sale": sale, "rows": rows, "next_status": next_status,
        "cash_transactions": cash_transactions,
        "can_cancel": not sale.is_cancelled and (
            request.user.is_superuser or request.user.has_perm("sales.cancel_sale")
        ),
    })


@permission_required_any("sales.edit_unpaid_postpay_sale")
def sale_edit(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related("cd_items", "tech_items"), pk=pk)
    if not sale.is_postpay_editable:
        messages.error(request, "Состав этой продажи изменять нельзя.")
        return _sale_destination(request, sale)
    initial_items = [
        {"product_type": "cd", "product_id": item.cd_id, "quantity": item.quantity,
         "label": f"CD — {item.product_name_snapshot}"}
        for item in sale.cd_items.all()
    ] + [
        {"product_type": "tech", "product_id": item.tech_id, "quantity": item.quantity,
         "label": f"Tech — {item.product_name_snapshot}"}
        for item in sale.tech_items.all()
    ]
    if request.method == "POST":
        try:
            edit_postpay_sale_items(actor=request.user, sale_id=sale.pk, lines=_parse_lines(request.POST))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Состав продажи обновлён.")
            return _sale_destination(request, sale)
    return render(request, "sales/edit.html", {"sale": sale, "initial_items": initial_items})


@require_POST
@permission_required_any("sales.advance_order_status")
def sale_advance(request, pk):
    try:
        advance_order_status(actor=request.user, sale_id=pk, next_status=request.POST.get("next_status", ""))
    except (ValidationError, Sale.DoesNotExist) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Продажа не найдена.")
    else:
        messages.success(request, "Статус заказа изменён.")
    sale = Sale.objects.filter(pk=pk).first()
    return _sale_destination(request, sale) if sale else redirect("core:home")


@require_POST
@permission_required_any("sales.mark_sale_paid")
def sale_mark_paid(request, pk):
    try:
        mark_sale_paid(actor=request.user, sale_id=pk)
    except (ValidationError, Sale.DoesNotExist) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Продажа не найдена.")
    else:
        messages.success(request, "Оплата подтверждена.")
    sale = Sale.objects.filter(pk=pk).first()
    return _sale_destination(request, sale) if sale else redirect("core:home")


@require_POST
@permission_required_any("sales.cancel_sale")
def sale_cancel(request, pk):
    try:
        result = cancel_sale(
            actor=request.user, sale_id=pk, comment=request.POST.get("cancellation_comment"),
        )
    except (ValidationError, Sale.DoesNotExist) as exc:
        messages.error(
            request,
            " ".join(exc.messages) if isinstance(exc, ValidationError) else "Продажа не найдена.",
        )
    else:
        if result.cancelled:
            messages.success(request, f"Продажа {result.sale.visible_id} отменена.")
        else:
            messages.info(request, "Продажа уже была отменена ранее.")
    sale = Sale.objects.filter(pk=pk).first()
    return _sale_destination(request, sale) if sale else redirect("core:home")
