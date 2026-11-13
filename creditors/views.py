"""HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны."""
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from core.decorators import permission_required_any, permission_required_all
from .forms import CreditorCreateForm, CreditorEditForm, DebtAdjustmentForm, PrepaymentForm
from .models import Creditor, CreditorTransaction, PrepaymentTransaction
from .services import adjust_creditor_debt

logger = logging.getLogger("gamebat.business")


@permission_required_any("creditors.view_creditors")
def creditor_list(request):
    return render(request, "creditors/list.html", {
        "creditors": Creditor.objects.select_related('partner').annotate(
            debt_group=Case(
                When(current_debt__gt=0, then=Value(0)),
                When(current_debt__lt=0, then=Value(1)),
                default=Value(2), output_field=IntegerField(),
            ),
            list_name=Coalesce('partner__name', 'name'),
        ).order_by('debt_group', 'list_name', 'pk'),
        "can_add": request.user.is_superuser or request.user.has_perm("creditors.add_creditor"),
        "can_change_debt": request.user.is_superuser or request.user.has_perm("creditors.change_debt"),
    })


@permission_required_any("creditors.add_creditor")
def creditor_create(request):
    form = CreditorCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        creditor = form.save()
        logger.info("Кредитор создан: user_id=%s creditor_id=%s", request.user.pk, creditor.pk)
        messages.success(request, "Кредитор создан. Начальная задолженность — 0 ₽.")
        return redirect("creditors:detail", pk=creditor.pk)
    return render(request, "creditors/form.html", {"form": form, "title": "Создать нового кредитора"})


@permission_required_any("creditors.view_creditors")
def creditor_detail(request, pk):
    creditor = get_object_or_404(Creditor.objects.select_related('partner'), pk=pk)
    can_view_history = request.user.is_superuser or request.user.has_perm("creditors.view_history")
    return render(request, "creditors/detail.html", {
        "creditor": creditor,
        "transactions": creditor.transactions.select_related("warehouse", "actor", 'sale') if can_view_history else [],
        "prepayment_transactions": creditor.prepayment_transactions.select_related("warehouse", "actor", "sale") if can_view_history else [],
        "can_view_history": can_view_history,
        "can_change": request.user.is_superuser or request.user.has_perm("creditors.change_creditor"),
        "can_change_debt": request.user.is_superuser or request.user.has_perm("creditors.change_debt"),
    })


@permission_required_all("creditors.view_creditors", "creditors.view_history")
@require_GET
def creditor_operation(request, pk, prepayment=False):
    """Снимок конкретной проводки и её реальных связей; проведение здесь отсутствует."""
    model = PrepaymentTransaction if prepayment else CreditorTransaction
    linked = 'debt_transaction' if prepayment else 'prepayment_transaction'
    operation = get_object_or_404(model.objects.select_related(
        'creditor__partner', 'warehouse', 'actor', 'sale', 'reversal_of', 'reversal', linked), pk=pk)
    cash_operation = None
    if operation.cash_transaction_id and request.user.has_perm('cash.view_cash_history'):
        from cash.models import CashTransaction
        entry = CashTransaction.objects.select_related('cash_register__warehouse', 'safe', 'created_by').get(
            pk=operation.cash_transaction_id)
        if not entry.safe_id or request.user.has_perm('cash.view_safe'):
            cash_operation = entry
    return render(request, 'creditors/operation_detail.html', {
        'operation': operation, 'creditor': operation.creditor, 'prepayment': prepayment,
        'operation_route': 'creditors:prepayment_operation' if prepayment else 'creditors:operation',
        'old_amount': operation.old_balance if prepayment else operation.old_debt,
        'new_amount': operation.new_balance if prepayment else operation.new_debt,
        'related_operation': getattr(operation, linked, None),
        'related_route': 'creditors:operation' if prepayment else 'creditors:prepayment_operation',
        'reversed_by': getattr(operation, 'reversal', None),
        'cash_operation': cash_operation,
    })


@permission_required_any("creditors.change_creditor")
def creditor_edit(request, pk):
    creditor = get_object_or_404(Creditor, pk=pk)
    old_name, old_description = creditor.name, creditor.description
    form = CreditorEditForm(request.POST or None, instance=creditor)
    if request.method == "POST" and form.is_valid():
        creditor = form.save()
        logger.info(
            "Кредитор изменён: user_id=%s creditor_id=%s name_changed=%s description_changed=%s",
            request.user.pk, creditor.pk, old_name != creditor.name, old_description != creditor.description,
        )
        messages.success(request, "Данные кредитора обновлены.")
        return redirect("creditors:detail", pk=creditor.pk)
    return render(request, "creditors/form.html", {
        "form": form, "title": "Редактировать кредитора", "creditor": creditor,
    })


@permission_required_any("creditors.change_debt")
def creditor_debt(request, pk):
    creditor = get_object_or_404(Creditor, pk=pk)
    form = DebtAdjustmentForm(request.POST or None, initial={"new_debt": creditor.current_debt})
    if request.method == "POST" and form.is_valid():
        try:
            amount = {"debt_delta": form.cleaned_data["debt_delta"]} if form.cleaned_data["amount_mode"] == "change" else {
                "new_debt": form.cleaned_data["new_debt"],
            }
            adjust_creditor_debt(
                actor=request.user, creditor_id=creditor.pk,
                warehouse_id=form.cleaned_data["warehouse"].pk,
                money_source_type=form.cleaned_data["money_source_type"],
                **amount, comment=form.cleaned_data["comment"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Задолженность и денежное хранилище обновлены.")
            return redirect("creditors:detail", pk=creditor.pk)
    return render(request, "creditors/debt.html", {"creditor": creditor, "form": form})


@permission_required_any("creditors.change_debt")
def creditor_prepayment(request, pk, transfer=False):
    from .prepayments import fund_prepayment
    creditor = get_object_or_404(Creditor.objects.select_related("partner"), pk=pk,
                                 partner__is_archived=False)
    form = PrepaymentForm(request.POST or None, transfer=transfer,
        initial={"amount": -creditor.current_debt if transfer and creditor.current_debt < 0 else None})
    if request.method == "POST" and form.is_valid():
        try:
            fund_prepayment(actor=request.user, creditor_id=creditor.pk,
                warehouse_id=form.cleaned_data["warehouse"].pk, amount=form.cleaned_data["amount"],
                operation_key=form.cleaned_data["operation_key"], transfer=transfer,
                money_source_type=form.cleaned_data.get("money_source_type", "offset"),
                comment=form.cleaned_data["comment"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Предоплата зачислена. Задолженность перенесена без движения денег." if transfer else
                             "Предоплата зачислена на отдельный счёт партнёра.")
            return redirect("creditors:detail", pk=creditor.pk)
    return render(request, "creditors/prepayment.html", {"creditor": creditor, "form": form, "transfer": transfer})
