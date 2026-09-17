import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import permission_required_any
from .forms import CreditorCreateForm, CreditorEditForm, DebtAdjustmentForm
from .models import Creditor
from .services import adjust_creditor_debt

logger = logging.getLogger("gamebat.business")


@permission_required_any("creditors.view_creditors")
def creditor_list(request):
    return render(request, "creditors/list.html", {
        "creditors": Creditor.objects.all(),
        "can_add": request.user.is_superuser or request.user.has_perm("creditors.add_creditor"),
        "can_change": request.user.is_superuser or request.user.has_perm("creditors.change_creditor"),
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
    creditor = get_object_or_404(Creditor, pk=pk)
    can_view_history = request.user.is_superuser or request.user.has_perm("creditors.view_history")
    return render(request, "creditors/detail.html", {
        "creditor": creditor,
        "transactions": creditor.transactions.select_related("warehouse", "actor") if can_view_history else [],
        "can_view_history": can_view_history,
        "can_change": request.user.is_superuser or request.user.has_perm("creditors.change_creditor"),
        "can_change_debt": request.user.is_superuser or request.user.has_perm("creditors.change_debt"),
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
            adjust_creditor_debt(
                actor=request.user, creditor_id=creditor.pk,
                warehouse_id=form.cleaned_data["warehouse"].pk,
                money_source_type=form.cleaned_data["money_source_type"],
                new_debt=form.cleaned_data["new_debt"], comment=form.cleaned_data["comment"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Задолженность и денежное хранилище обновлены.")
            return redirect("creditors:detail", pk=creditor.pk)
    return render(request, "creditors/debt.html", {"creditor": creditor, "form": form})
