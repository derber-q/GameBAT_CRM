from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import permission_required_any
from .forms import SaleCreateForm
from .models import Sale
from .services import advance_order_status, create_sale, edit_postpay_sale_items, mark_sale_paid


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
        order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.PAID
    ) if (request.user.is_superuser or request.user.has_perm("sales.view_completed_sales")) else []
    incomplete = queryset.exclude(
        order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.PAID
    )
    return render(request, "sales/list.html", {
        "incomplete_sales": incomplete,
        "completed_sales": completed,
        "can_view_completed": request.user.is_superuser or request.user.has_perm("sales.view_completed_sales"),
    })


@permission_required_any("sales.create_sale")
def sale_create(request):
    form = SaleCreateForm(request.POST or None)
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
            messages.success(request, f"Продажа {sale.visible_id} создана.")
            return _sale_destination(request, sale)
    return render(request, "sales/create.html", {
        "form": form,
        "can_view_sales": request.user.is_superuser or request.user.has_perm("sales.view_sales"),
    })


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
    if not (request.user.is_superuser or request.user.has_perm("sales.advance_order_status")):
        next_status = None
    cash_transaction = None
    if request.user.is_superuser or request.user.has_perm("cash.view_cash_history"):
        try:
            cash_transaction = sale.cash_transaction
        except ObjectDoesNotExist:
            pass
    return render(request, "sales/detail.html", {
        "sale": sale, "rows": rows, "next_status": next_status, "cash_transaction": cash_transaction,
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
