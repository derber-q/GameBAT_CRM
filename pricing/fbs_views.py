"""Предпросмотр, сохранение расчёта и явное применение к отправляемой цене."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from catalog.nomenclature_forms import product_version
from core.decorators import permission_required_any
from yandex_market.fbs_pricing import INPUT_FIELDS, product_calculation, save_product_inputs
from yandex_market.pricing_forms import FBSProductForm
from .services import update_product_prices


def product_for(kind, pk):
    from django.http import Http404
    model = {"cd": CD, "tech": Tech}.get(kind)
    if model is None:
        raise Http404
    return get_object_or_404(model.objects.active().select_related("yandex_pricing_integration", "yandex_pricing_category"), pk=pk)


@permission_required_any("pricing.view_pricing")
def detail(request, kind, pk):
    product = product_for(kind, pk)
    form = FBSProductForm(product=product, user=request.user)
    template = "pricing/_fbs_form.html" if request.GET.get("partial") == "1" else "pricing/fbs_detail.html"
    return render(request, template, {"product": product, "kind": kind, "form": form,
                  "result": product_calculation(product, log_errors=False),
                  "can_apply": request.user.is_superuser or request.user.has_perm("pricing.change_yandex_market_price")})


@require_POST
@permission_required_any("pricing.view_pricing")
def preview(request, kind, pk):
    product = product_for(kind, pk)
    if request.POST.get("inline") == "1":
        if set(request.POST) - {"inline", "yandex_desired_profit", "csrfmiddlewaretoken"}:
            return JsonResponse({"ok": False, "message": "Некорректные параметры предпросмотра."}, status=400)
        try:
            profit = product._meta.get_field("yandex_desired_profit").clean(request.POST.get("yandex_desired_profit") or None, product)
        except ValidationError as exc:
            return JsonResponse({"ok": False, "message": " ".join(exc.messages)}, status=400)
        return JsonResponse(product_calculation(product, overrides={"yandex_desired_profit": profit}))
    form = FBSProductForm(request.POST, product=product, user=request.user)
    if not form.is_valid():
        return JsonResponse({"ok": False, "message": " ".join(str(e) for errors in form.errors.values() for e in errors)}, status=400)
    data = form.cleaned_data
    result = product_calculation(product, integration=data.get("yandex_pricing_integration"), category=data.get("yandex_pricing_category"), overrides=data)
    return JsonResponse(result)


@require_POST
@permission_required_any("pricing.view_pricing")
def save(request, kind, pk):
    product = product_for(kind, pk)
    form = FBSProductForm(request.POST, product=product, user=request.user)
    if not form.is_valid():
        return JsonResponse({"ok": False, "message": " ".join(str(e) for errors in form.errors.values() for e in errors)}, status=400)
    action = request.POST.get("action", "save")
    if action not in {"save", "apply"}:
        return JsonResponse({"ok": False, "message": "Неизвестное действие."}, status=400)
    if not form.can_edit or (action == "apply" and not (request.user.is_superuser or request.user.has_perm("pricing.change_yandex_market_price"))):
        return JsonResponse({"ok": False, "message": "Нет права сохранять или применять цену FBS."}, status=403)
    try:
        with transaction.atomic():
            product, result = save_product_inputs(actor=request.user, product=product,
                changes={field: form.cleaned_data[field] for field in form.allowed_fields}, version=form.cleaned_data["version"])
            if action == "apply":
                if not result["ok"]:
                    raise ValidationError(result["message"])
                product = update_product_prices(actor=request.user, product_type=kind, product_id=pk, changes={"yandex_market_price": result["final_price"]})
    except ValidationError as exc:
        return JsonResponse({"ok": False, "message": " ".join(exc.messages)}, status=400)
    return JsonResponse({"ok": True, "calculation": result, "version": product_version(product),
                        "dimensions_complete": all(getattr(product, field) for field in ("length_cm", "width_cm", "height_cm")),
                        "applied_price": product.yandex_market_price if action == "apply" else None,
                        "message": "Цена применена. Используется существующая синхронизация Маркета." if action == "apply" else "Параметры расчёта сохранены."})
