from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
import logging

from .forms import SupplierForm
from .models import Supplier

logger = logging.getLogger("gamebat.business")


@permission_required("partners.view_supplier", raise_exception=True)
def supplier_list(request):
    full_access = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    if full_access:
        suppliers = list(Supplier.objects.values(
            "id", "letter", "highlight_color", "name", "legal_entity", "phone_1", "email", "telegram", "priority"
        ))
    else:
        # В шаблон попадают только безопасные поля — контакты не скрываются CSS, а отсутствуют в HTML.
        suppliers = list(Supplier.objects.values("id", "letter", "highlight_color"))
    return render(request, "partners/supplier_list.html", {"suppliers": suppliers, "full_access": full_access})


@permission_required("partners.add_supplier", raise_exception=True)
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        logger.info(
            "Поставщик создан: user_id=%s supplier_id=%s priority=%s",
            request.user.pk, supplier.pk, supplier.priority,
        )
        messages.success(request, "Поставщик добавлен.")
        return redirect("partners:list")
    return render(request, "partners/supplier_form.html", {"form": form, "title": "Добавить поставщика"})


@permission_required("partners.change_supplier", raise_exception=True)
@permission_required("partners.view_supplier_details", raise_exception=True)
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        old_priority = supplier.priority
        supplier = form.save()
        logger.info(
            "Поставщик изменён: user_id=%s supplier_id=%s priority=%s old_priority=%s fields=%s",
            request.user.pk, supplier.pk, supplier.priority, old_priority, ",".join(form.changed_data),
        )
        messages.success(request, "Поставщик обновлён.")
        return redirect("partners:list")
    return render(request, "partners/supplier_form.html", {"form": form, "title": "Редактировать поставщика"})
