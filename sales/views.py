from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, OperationalError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from core.decorators import permission_required_all, permission_required_any
from price.excel import import_wholesale_price_to_sale
from .forms import SaleCreateForm, WholesalePriceImportForm
from .models import Sale
from .listing import list_groups, sales_queryset, status_context
from .services import (
    advance_order_status, cancel_sale, create_sale, edit_postpay_sale_items,
    mark_sale_paid, update_sale_note, next_order_status,
)


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
    return _sale_list_page(request, 'incomplete', 'Незавершённые продажи')


def _sale_list_page(request, state, title):
    return render(request, 'sales/list.html', {
        'state': state, 'page_title': title, 'groups': list_groups(request, state),
    })


@permission_required_all('sales.view_sales', 'sales.view_completed_sales')
def sale_completed_list(request):
    return _sale_list_page(request, 'completed', 'Завершённые продажи')


@permission_required_any('sales.view_sales')
def sale_cancelled_list(request):
    return _sale_list_page(request, 'cancelled', 'Отменённые продажи')


def _status_response(request, pk, success, message, status=200):
    sale = sales_queryset().filter(pk=pk).first()
    data = {'success': success, 'message': message}
    if sale:
        data.update(
            order_status=sale.order_status, payment_status=sale.payment_status,
            is_completed=sale.is_completed, is_cancelled=sale.is_cancelled,
            version=sale.updated_at.isoformat(),
            row_html=render_to_string('sales/_list_row.html', {
                'row': status_context(sale, request.user), 'state': 'incomplete',
            }, request=request),
        )
    return JsonResponse(data, status=status)


@require_POST
@permission_required_any('sales.view_sales')
def sale_inline_status(request, pk):
    field = request.POST.get('field')
    permission = {'order': 'sales.advance_order_status', 'payment': 'sales.mark_sale_paid'}.get(field)
    if not permission:
        return _status_response(request, pk, False, 'Неизвестный статус.', 400)
    if not (request.user.is_superuser or request.user.has_perm(permission)):
        return _status_response(request, pk, False, 'Недостаточно прав для изменения статуса.', 403)
    if request.POST.get('confirmed') != '1':
        return _status_response(request, pk, False, 'Подтвердите изменение статуса.', 400)
    try:
        with transaction.atomic():
            sale = Sale.objects.select_for_update().get(pk=pk)
            if sale.is_cancelled or sale.is_completed:
                return _status_response(request, pk, False, 'Продажа уже завершена или отменена.', 409)
            if request.POST.get('version') != sale.updated_at.isoformat():
                return _status_response(request, pk, False, 'Продажа изменена другим пользователем. Проверьте актуальные данные и повторите действие.', 409)
            if field == 'order':
                advance_order_status(actor=request.user, sale_id=pk, next_status=request.POST.get('value', ''))
            else:
                if request.POST.get('value') != Sale.PaymentStatus.PAID:
                    raise ValidationError('Этот переход статуса оплаты недопустим.')
                mark_sale_paid(actor=request.user, sale_id=pk, cash_received_amount=request.POST.get('cash_received_amount'))
    except Sale.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Продажа не найдена.'}, status=404)
    except ValidationError as exc:
        return _status_response(request, pk, False, ' '.join(exc.messages), 400)
    except OperationalError:
        return _status_response(request, pk, False, 'База занята другим изменением. Проверьте статус и повторите действие.', 409)
    return _status_response(request, pk, True, 'Статус сохранён.')


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
                cash_received_amount=form.cleaned_data["cash_received_amount"],
                note=form.cleaned_data["note"],
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
    next_order = next_order_status(sale)
    labels = {
        Sale.OrderStatus.ASSEMBLED: "Отметить как собранный",
        Sale.OrderStatus.SHIPPED: "Отметить как отправленный",
        Sale.OrderStatus.DELIVERED: "Отметить как доставленный",
    }
    next_status = (next_order, labels[next_order]) if next_order else None
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
        "can_edit_note": request.user.is_superuser or request.user.has_perm("sales.change_sale"),
    })


@permission_required_any("sales.edit_unpaid_postpay_sale")
def sale_edit(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related("cd_items", "tech_items"), pk=pk)
    if not sale.is_postpay_editable:
        messages.error(request, "Состав этой продажи изменять нельзя.")
        return _sale_destination(request, sale)
    initial_items = [
        {"product_type": "cd", "product_id": item.cd_id, "quantity": item.quantity,
         "label": f"CD — {item.product_name_snapshot}", "unit_price": f"{item.unit_price:.2f}"}
        for item in sale.cd_items.all()
    ] + [
        {"product_type": "tech", "product_id": item.tech_id, "quantity": item.quantity,
         "label": f"Tech — {item.product_name_snapshot}", "unit_price": f"{item.unit_price:.2f}"}
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
        mark_sale_paid(
            actor=request.user, sale_id=pk,
            cash_received_amount=request.POST.get("cash_received_amount"),
        )
    except (ValidationError, Sale.DoesNotExist) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Продажа не найдена.")
    else:
        messages.success(request, "Оплата подтверждена.")
    sale = Sale.objects.filter(pk=pk).first()
    return _sale_destination(request, sale) if sale else redirect("core:home")


@require_POST
@permission_required_any("sales.change_sale")
def sale_note_update(request, pk):
    try:
        sale = update_sale_note(actor=request.user, sale_id=pk, note=request.POST.get("note"))
    except Sale.DoesNotExist:
        messages.error(request, "Продажа не найдена.")
        return redirect("sales:list")
    messages.success(request, "Примечание сохранено.")
    return _sale_destination(request, sale)


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
