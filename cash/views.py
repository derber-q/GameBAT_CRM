import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import permission_required_any
from warehouse.models import Warehouse
from .forms import CashOperationForm
from .models import CashRegister, CashTransaction, Safe
from .services import (
    collect_cash,
    collect_safe,
    deposit_cash,
    deposit_safe,
    transfer_cash_to_safe,
    transfer_safe_to_cash,
)


def _cash_destination(request, warehouse):
    if (
        request.user.is_superuser
        or request.user.has_perm("cash.view_cash_register")
        or request.user.has_perm("cash.view_cash_history")
        or request.user.has_perm("cash.view_safe")
    ):
        return redirect("cash:register", warehouse_pk=warehouse.pk)
    if (
        request.user.has_perm("warehouse.view_warehouse_stock")
        or request.user.has_perm("catalog.view_cd")
        or request.user.has_perm("catalog.view_tech")
    ):
        return redirect("warehouse:detail", pk=warehouse.pk)
    return redirect("core:home")


@permission_required_any("cash.view_cash_register", "cash.view_cash_history", "cash.view_safe")
def register_detail(request, warehouse_pk):
    warehouse = get_object_or_404(Warehouse, pk=warehouse_pk)
    register = get_object_or_404(CashRegister, warehouse=warehouse)
    can_view_cash_balance = request.user.is_superuser or request.user.has_perm("cash.view_cash_register")
    can_view_safe = request.user.is_superuser or request.user.has_perm("cash.view_safe")
    can_view_history = request.user.is_superuser or request.user.has_perm("cash.view_cash_history")
    safe = get_object_or_404(Safe, warehouse=warehouse)
    transactions = []
    if can_view_history:
        transactions = register.transactions.select_related("created_by", "sale", "safe")
        if not can_view_safe:
            transactions = transactions.filter(safe__isnull=True)
        transactions = transactions[:20]
    return render(request, "cash/register.html", {
        "warehouse": warehouse,
        "register": register,
        "safe": safe if can_view_safe else None,
        "transactions": transactions,
        "can_view_cash_balance": can_view_cash_balance,
        "can_view_safe": can_view_safe,
        "can_view_history": can_view_history,
        "can_view_total": can_view_cash_balance and can_view_safe,
        "total_balance": register.balance + safe.balance if can_view_cash_balance and can_view_safe else None,
    })


def _operation(
    request, warehouse_pk, *, service, title, permission, storage_label="Касса",
    requires_safe_view=False,
):
    if not (request.user.is_superuser or request.user.has_perm(permission)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("У вас нет доступа к этому действию.")
    if requires_safe_view and not (
        request.user.is_superuser or request.user.has_perm("cash.view_safe")
    ):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("У вас нет доступа к сейфу.")
    warehouse = get_object_or_404(Warehouse, pk=warehouse_pk)
    form = CashOperationForm(
        request.POST or None,
        initial={"operation_key": uuid.uuid4()} if request.method != "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            service(actor=request.user, warehouse_id=warehouse.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            # Уникальный ключ формы не позволяет параллельному повторному POST
            # провести ту же операцию второй раз. Исходная транзакция уже откатилась.
            operation_key = form.cleaned_data.get("operation_key")
            if not operation_key or not CashTransaction.objects.filter(operation_key=operation_key).exists():
                raise
            messages.info(request, "Эта денежная операция уже была проведена.")
            return _cash_destination(request, warehouse)
        else:
            messages.success(request, "Денежная операция проведена.")
            return _cash_destination(request, warehouse)
    return render(request, "cash/operation.html", {
        "form": form,
        "warehouse": warehouse,
        "title": title,
        "storage_label": storage_label,
        "can_view_register": (
            request.user.is_superuser
            or request.user.has_perm("cash.view_cash_register")
            or request.user.has_perm("cash.view_cash_history")
            or request.user.has_perm("cash.view_safe")
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


@permission_required_any("cash.deposit_safe")
def safe_deposit(request, warehouse_pk):
    return _operation(
        request, warehouse_pk, service=deposit_safe,
        title="Внести в сейф", permission="cash.deposit_safe", storage_label="Сейф",
        requires_safe_view=True,
    )


@permission_required_any("cash.collect_safe")
def safe_collect(request, warehouse_pk):
    return _operation(
        request, warehouse_pk, service=collect_safe,
        title="Инкассировать из сейфа", permission="cash.collect_safe", storage_label="Сейф",
        requires_safe_view=True,
    )


@permission_required_any("cash.transfer_cash_to_safe")
def cash_to_safe(request, warehouse_pk):
    return _operation(
        request, warehouse_pk, service=transfer_cash_to_safe,
        title="Передать из кассы в сейф", permission="cash.transfer_cash_to_safe",
        storage_label="Касса → Сейф", requires_safe_view=True,
    )


@permission_required_any("cash.transfer_safe_to_cash")
def safe_to_cash(request, warehouse_pk):
    return _operation(
        request, warehouse_pk, service=transfer_safe_to_cash,
        title="Передать из сейфа в кассу", permission="cash.transfer_safe_to_cash",
        storage_label="Сейф → Касса", requires_safe_view=True,
    )
