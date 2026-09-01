from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SupplierForm
from .models import Supplier


@permission_required("partners.view_supplier", raise_exception=True)
def supplier_list(request):
    full_access = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    if full_access:
        suppliers = list(Supplier.objects.values(
            "id", "letter", "highlight_color", "name", "legal_entity", "phone_1", "email", "telegram"
        ))
    else:
        # В шаблон попадают только безопасные поля — контакты не скрываются CSS, а отсутствуют в HTML.
        suppliers = list(Supplier.objects.values("id", "letter", "highlight_color"))
    return render(request, "partners/supplier_list.html", {"suppliers": suppliers, "full_access": full_access})


@permission_required("partners.add_supplier", raise_exception=True)
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Поставщик добавлен.")
        return redirect("partners:list")
    return render(request, "partners/supplier_form.html", {"form": form, "title": "Добавить поставщика"})


@permission_required("partners.change_supplier", raise_exception=True)
@permission_required("partners.view_supplier_details", raise_exception=True)
def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Поставщик обновлён.")
        return redirect("partners:list")
    return render(request, "partners/supplier_form.html", {"form": form, "title": "Редактировать поставщика"})
