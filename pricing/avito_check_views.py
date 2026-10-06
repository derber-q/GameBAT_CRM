"""Последовательная ручная проверка цен связанных с Avito товаров."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from catalog.audit import record_product_changes
from catalog.models import CD, Tech, ProductChangeEvent
from catalog.product_search import filter_products_by_text
from core.decorators import permission_required_all, permission_required_any
from integrations.avito_check import display_result, manual_search_url, queue, run_check
from integrations.models import AvitoManualPrice, AvitoPriceCheckResult, ReefApiCredential
from integrations.reef_api import ReefApiError
from .services import update_product_prices
from .warnings import product_price_warnings


def _item(kind, pk, items=None):
    items = items if items is not None else queue()
    return next(((index, product) for index, (current_kind, product) in enumerate(items)
                 if current_kind == kind and product.pk == pk), (None, None))


def _page_context(request, items, index, *, posted=None):
    kind, product = items[index]
    return {
        "kind": kind, "product": product, "index": index, "total": len(items),
        "result": display_result(product, kind),
        "manual_search_url": manual_search_url(product, kind),
        "warnings": product_price_warnings(product),
        "form_wholesale": posted.get("wholesale_price", "") if posted is not None else product.wholesale_price,
        "form_avito": posted.get("avito_price", "") if posted is not None else product.avito_price,
        "reef_configured": ReefApiCredential.objects.filter(pk=1).exclude(encrypted_api_key="").exists(),
        "can_change_avito": request.user.is_superuser or request.user.has_perm("pricing.change_retail_price"),
        "can_change_wholesale": request.user.is_superuser or request.user.has_perm("pricing.change_wholesale_price"),
    }


@require_GET
@permission_required_any("pricing.view_pricing")
def page(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "name")
    if sort not in {"name", "oldest", "newest"}:
        sort = "name"
    can_change_avito = request.user.is_superuser or request.user.has_perm("pricing.change_retail_price")
    can_change_wholesale = request.user.is_superuser or request.user.has_perm("pricing.change_wholesale_price")
    rows = []
    products = CD.objects.filter(avito_profile__connection__isnull=False).select_related(
        "avito_profile__manual_price", "platform", "game_series",
    ).annotate(physical_stock=Sum("warehouse_stocks__quantity")).filter(physical_stock__gt=0).order_by("name", "pk")
    if query:
        products = filter_products_by_text(products, query, product_kind="cd")
    for product in products:
        found = getattr(product.avito_profile, "manual_price", None)
        rows.append({"kind": "cd", "type": "cd", "product": product, "found": found,
                     "warnings": product_price_warnings(product),
                     "can_change_avito": can_change_avito and not product.is_archived,
                     "can_change_wholesale": can_change_wholesale and not product.is_archived,
                     "manual_url": manual_search_url(product, "cd")})
    rows.sort(key=lambda row: (row["product"].name.casefold(), row["kind"], row["product"].pk))
    if sort != "name":
        dated = [row for row in rows if row["found"] is not None]
        undated = [row for row in rows if row["found"] is None]
        dated.sort(key=lambda row: row["found"].recorded_at, reverse=sort == "newest")
        rows = dated + undated
    return render(request, "pricing/avito_check_list.html", {
        "rows": rows, "query": query, "sort": sort, "total": len(rows),
        "can_record": can_change_avito,
    })


@require_POST
@permission_required_all("pricing.view_pricing", "pricing.change_retail_price")
def save_found_price(request):
    kind = request.POST.get("kind")
    model = {"cd": CD, "tech": Tech}.get(kind)
    try:
        pk = int(request.POST.get("product_id", ""))
        value = _parse_price(request.POST.get("price", "").strip().replace(",", "."))
        if model is None or value is None or value <= 0:
            raise ValidationError("Укажите найденную цену больше нуля.")
        with transaction.atomic():
            product = model.objects.select_related("avito_profile").get(pk=pk, avito_profile__connection__isnull=False)
            previous = AvitoManualPrice.objects.select_for_update().filter(profile=product.avito_profile).first()
            old_price = str(previous.price) if previous else ""
            recorded_at = timezone.now()
            found, _ = AvitoManualPrice.objects.update_or_create(profile=product.avito_profile, defaults={
                "price": value, "recorded_at": recorded_at, "recorded_by": request.user,
            })
            record_product_changes(actor=request.user, instance=product, source=ProductChangeEvent.Source.CRM, changes=[
                {"field_name": "avito_found_price", "field_label": "Найденная минимальная цена Avito",
                 "old_value": old_price, "new_value": str(value)},
                {"field_name": "avito_found_price_at", "field_label": "Дата ручной проверки Avito",
                 "old_value": previous.recorded_at.isoformat() if previous else "", "new_value": recorded_at.isoformat()},
            ])
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({"ok": False, "message": " ".join(exc.messages) if isinstance(exc, ValidationError) else "Некорректные данные."}, status=400)
    except (CD.DoesNotExist, Tech.DoesNotExist):
        return JsonResponse({"ok": False, "message": "Товар не найден или больше не связан с Avito."}, status=404)
    return JsonResponse({"ok": True, "price": str(found.price),
                         "recorded_at": timezone.localtime(found.recorded_at).strftime("%d.%m.%Y %H:%M")})


@require_GET
@permission_required_any("pricing.view_pricing")
def automatic_page(request):
    items = queue()
    try:
        index = int(request.GET.get("index", "0"))
    except ValueError:
        index = 0
    if index < 0:
        index = 0
    if not items or index >= len(items):
        return render(request, "pricing/avito_check_complete.html", {"total": len(items)})
    return render(request, "pricing/avito_check.html", _page_context(request, items, index))


def _parse_price(value):
    if value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную цену.") from exc
    if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2 or number >= Decimal("1000000000000000000"):
        raise ValidationError("Укажите корректную цену в рублях и копейках.")
    return number


@require_POST
@permission_required_any("pricing.view_pricing")
def next_product(request):
    kind = request.POST.get("kind", "")
    try:
        pk = int(request.POST.get("product_id", ""))
    except (TypeError, ValueError):
        return redirect("pricing:avito_check_automatic")
    items = queue()
    index, product = _item(kind, pk, items)
    if product is None:
        messages.error(request, "Товар выбыл из очереди. Список обновлён.")
        return redirect("pricing:avito_check_automatic")
    changes = {}
    try:
        for field, permission in (("wholesale_price", "pricing.change_wholesale_price"), ("avito_price", "pricing.change_retail_price")):
            value = _parse_price(request.POST.get(field, ""))
            if value != getattr(product, field):
                if not (request.user.is_superuser or request.user.has_perm(permission)):
                    raise PermissionDenied("У вас нет права изменять эту цену.")
                changes[field] = "" if value is None else str(value)
        if changes:
            update_product_prices(actor=request.user, product_type=kind, product_id=pk, changes=changes)
    except ValidationError as exc:
        context = _page_context(request, items, index, posted=request.POST)
        context["form_error"] = " ".join(exc.messages)
        return render(request, "pricing/avito_check.html", context, status=400)
    messages.success(request, "Цены сохранены." if changes else "Переход к следующему товару.")
    return redirect(f"{reverse('pricing:avito_check_automatic')}?index={index + 1}")


@require_POST
@permission_required_any("pricing.view_pricing")
def check_product(request):
    action = request.POST.get("action", "check")
    if action not in {"check", "refresh", "deep"}:
        return JsonResponse({"ok": False, "message": "Неизвестный режим проверки."}, status=400)
    kind = request.POST.get("kind", "")
    try:
        pk = int(request.POST.get("product_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Товар не найден."}, status=404)
    _, product = _item(kind, pk)
    if product is None:
        return JsonResponse({"ok": False, "message": "Товар выбыл из очереди."}, status=404)
    lock_key = f"avito_check:{kind}:{pk}"
    if not cache.add(lock_key, True, timeout=900):
        return JsonResponse({"ok": False, "message": "Проверка этого товара уже выполняется."}, status=409)
    try:
        previous = display_result(product, kind)
        run_check(product, kind, mode="deep" if action == "deep" else "economy", force=action == "refresh")
    except ReefApiError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=502)
    finally:
        cache.delete(lock_key)
    result = AvitoPriceCheckResult.objects.get(profile=product.avito_profile)
    reused = previous is not None and previous.checked_at == result.checked_at
    message = "Показана сохранённая проверка за последние сутки. Расход: 0 кредитов." if reused else "Проверка завершена."
    return JsonResponse({"ok": True, "message": message, "html": render_to_string("pricing/_avito_check_results.html", {"result": result}, request=request)})
