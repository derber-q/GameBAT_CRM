"""Мобильная ревизия локального склада и защищённые действия."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_any
from .models import Warehouse, WarehouseRevision
from .revision_services import allowed_kinds, grouped_rows, progress, revision_rows, set_checked, start_revision


ACCESS = ("warehouse.view_warehouse_stock", "catalog.view_cd", "catalog.view_tech")


@require_GET
@permission_required_any(*ACCESS)
def revision_page(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    revision = WarehouseRevision.objects.filter(warehouse=warehouse, is_active=True).first()
    mode = "locations" if request.GET.get("mode") == "locations" else "products"
    kinds = allowed_kinds(request.user)
    rows = revision_rows(warehouse=warehouse, revision=revision, kinds=kinds)
    return render(request, "warehouse/revision.html", {
        "warehouse": warehouse, "revision": revision, "mode": mode,
        "groups": grouped_rows(rows, mode), "progress": progress(rows),
        "partial_access": len(kinds) != 2,
        "can_start": request.user.is_superuser or request.user.has_perm("warehouse.view_warehouse_stock"),
    })


@require_POST
@permission_required_any("warehouse.view_warehouse_stock")
def revision_start(request, pk):
    get_object_or_404(Warehouse, pk=pk)
    try:
        if request.POST.get("confirm") != "yes":
            raise ValidationError("Подтвердите начало новой ревизии.")
        expected = request.POST.get("revision_id", "")
        start_revision(warehouse_id=pk, actor=request.user, expected_revision_id=int(expected) if expected else None)
    except (ValueError, ValidationError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Некорректный номер ревизии.")
    else:
        messages.success(request, "Новая ревизия начата. Отметки предыдущего цикла сохранены в истории.")
    return redirect("warehouse:revision", pk=pk)


@require_POST
@permission_required_any(*ACCESS)
def revision_check(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    try:
        if request.POST.get("checked") not in {"true", "false"}:
            raise ValueError
        raw_revision_id = request.POST.get("revision_id", "")
        item = set_checked(warehouse_id=pk, revision_id=int(raw_revision_id) if raw_revision_id else None,
                           kind=request.POST.get("kind"), product_id=int(request.POST.get("product_id", "")),
                           checked=request.POST["checked"] == "true", actor=request.user)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Некорректные данные отметки."}, status=400)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "message": " ".join(exc.messages)}, status=409)
    revision = WarehouseRevision.objects.filter(warehouse=warehouse, is_active=True).first()
    if not revision or revision.pk != item.revision_id:
        return JsonResponse({"ok": False, "message": "Начат новый цикл ревизии. Обновите страницу."}, status=409)
    rows = revision_rows(warehouse=warehouse, revision=revision, kinds=allowed_kinds(request.user))
    row = next((row for row in rows if row["kind"] == request.POST["kind"] and row["product"].pk == int(request.POST["product_id"])), None)
    if row is None:
        return JsonResponse({"ok": False, "message": "Остаток изменился. Обновите страницу."}, status=409)
    return JsonResponse({"ok": True, "revision_id": revision.pk, "checked": row["checked"], "quantity": row["quantity"], "progress": progress(rows)})
