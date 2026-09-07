from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import permission_required_any
from warehouse.models import Warehouse
from .forms import CashOperationForm
from .models import CashRegister
from .services import collect_cash, deposit_cash


def _cash_destination(request, warehouse):
    if (
        request.user.is_superuser
        or request.user.has_perm("cash.view_cash_register")
        or request.user.has_perm("cash.view_cash_history")
    ):
        return redirect("cash:register", warehouse_pk=warehouse.pk)
    if (
        request.user.has_perm("warehouse.view_warehouse_stock")
        or request.user.has_perm("catalog.view_cd")
        or request.user.has_perm("catalog.view_tech")
    ):
        return redirect("warehouse:detail", pk=warehouse.pk)
    return redirect("core:home")


@permission_required_any("cash.view_cash_register", "cash.view_cash_history")
def register_detail(request, warehouse_pk):
    warehouse = get_object_or_404(Warehouse, pk=warehouse_pk)
    register = get_object_or_404(CashRegister, warehouse=warehouse)
    transactions = register.transactions.select_related("created_by", "sale")[:20] if (
        request.user.is_superuser or request.user.has_perm("cash.view_cash_history")
    ) else []
    return render(request, "cash/register.html", {
        "warehouse": warehouse,
        "register": register,
        "transactions": transactions,
        "can_view_balance": request.user.is_superuser or request.user.has_perm("cash.view_cash_register"),
    })


def _operation(request, warehouse_pk, *, service, title, permission):
    if not (request.user.is_superuser or request.user.has_perm(permission)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("У вас нет доступа к этому действию.")
    warehouse = get_object_or_404(Warehouse, pk=warehouse_pk)
    form = CashOperationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            service(actor=request.user, warehouse_id=warehouse.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Кассовая операция проведена.")
            return _cash_destination(request, warehouse)
    return render(request, "cash/operation.html", {
        "form": form,
        "warehouse": warehouse,
        "title": title,
        "can_view_register": (
            request.user.is_superuser
            or request.user.has_perm("cash.view_cash_register")
            or request.user.has_perm("cash.view_cash_history")
        ),
    })


@permission_required_any("cash.deposit_cash")
def deposit(request, warehouse_pk):
    return _operation(
        request, warehouse_pk, service=deposit_cash, title="Внести наличные", permission="cash.deposit_cash"
    )


@permission_required_any("cash.collect_cash")
def collect(request, warehouse_pk):
    return _operation(
        request, warehouse_pk, service=collect_cash, title="Инкассировать", permission="cash.collect_cash"
    )
