"""Последовательная ручная проверка цен связанных с Avito товаров."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, OperationalError
from django.db.models import Sum
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from catalog.audit import record_product_changes
from catalog.models import CD, Tech, ProductChangeEvent
from core.decorators import permission_required_all, permission_required_any
from integrations.avito_check import display_result, manual_search_url, queue, run_check
from integrations.models import AvitoManualPrice, AvitoPriceCheckResult, ReefApiCredential
from integrations.reef_api import ReefApiError
from .services import update_product_prices
from .avito_check_catalog import (
    SCOPES, SCOPE_LABELS, WARNING, found_prices, import_costs, listed_products, manual_product_data,
)
from core.db_retry import retry_database_lock
from .warnings import product_price_warnings, wholesale_margin


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
        "wholesale_margin": wholesale_margin(product.wholesale_price, product.cost),
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
    products = listed_products(query=query, sort=sort)
    latest_price, costs = import_costs()
    for product in products:
        kind = product._meta.model_name
        prices = found_prices(product)
        regions = [{
            'scope': scope, 'label': SCOPE_LABELS[scope], 'found': prices.get(scope),
            'version': prices[scope].recorded_at.isoformat() if scope in prices else '',
            'manual_url': manual_search_url(product, kind, scope),
        } for scope in SCOPES]
        rows.append({"kind": kind, "type": kind, "product": product, "regions": regions,
                     "import_cost": costs.get((kind, product.pk)),
                     "scope_warning": WARNING if all(k in prices for k in SCOPES) and prices['russia'].price > prices['rostov'].price else "",
                     "wholesale_margin": wholesale_margin(product.wholesale_price, product.cost),
                     "warnings": product_price_warnings(product),
                     "can_change_avito": can_change_avito and not product.is_archived,
                     "can_change_wholesale": can_change_wholesale and not product.is_archived})
    return render(request, "pricing/avito_check_list.html", {
        "rows": rows, "query": query, "sort": sort, "total": len(rows),
        "can_record": can_change_avito, "latest_import_price": latest_price,
    })


@require_GET
@never_cache
@permission_required_all('pricing.view_pricing', 'pricing.change_retail_price')
def manual_context(request):
    if settings.GAMEBAT_ENV == 'local_test':
        return JsonResponse({'ok':False, 'message':'ТЕСТОВЫЙ РЕЖИМ: живой сценарий расширения запрещён.'}, status=403)
    product_id = request.GET.get('product_id')
    kind, scope = request.GET.get('kind'), request.GET.get('scope')
    if product_id is not None:
        if not product_id.isascii() or not product_id.isdecimal() or len(product_id) > 18:
            return JsonResponse({'ok': False, 'message': 'Некорректный товар.'}, status=400)
        if kind not in ('cd', 'tech') or scope not in SCOPES:
            return JsonResponse({'ok': False, 'message': 'Обновите расширение: нужны тип товара и география.'}, status=400)
        products = listed_products(product_id=int(product_id), kind=kind)
        if not products:
            return JsonResponse({'ok': False, 'message': 'Товар выбыл из Avito Check: нет остатка или привязки.'}, status=404)
        data = {'product': manual_product_data(products[0], scope)}
    else:
        products = listed_products(query=request.GET.get('q', '').strip(), sort=request.GET.get('sort', 'name'))
        data = {'items': [manual_product_data(product, scope) for product in products for scope in SCOPES]}
    return JsonResponse({'ok': True, 'csrf_token': get_token(request), **data})


@require_POST
@permission_required_all("pricing.view_pricing", "pricing.change_retail_price")
def save_found_price(request):
    if settings.GAMEBAT_ENV == 'local_test' and request.POST.get('manual_queue') == '1':
        return JsonResponse({'ok':False, 'message':'ТЕСТОВЫЙ РЕЖИМ: запись из живого расширения запрещена.'},status=403)
    kind, scope = request.POST.get('kind'), request.POST.get('scope')
    model = {'cd': CD, 'tech': Tech}.get(kind)
    if model is None or scope not in SCOPES:
        return JsonResponse({'ok': False, 'message': 'Обновите страницу и расширение: укажите тип товара и географию.'}, status=400)
    try:
        product_id = request.POST.get('product_id', '')
        if not product_id.isascii() or not product_id.isdecimal() or len(product_id) > 18:
            raise ValidationError('Некорректный товар.')
        pk = int(product_id)
        value = _parse_price(request.POST.get('price', '').strip().replace(',', '.'))
        if value is None or value <= 0:
            raise ValidationError('Укажите найденную цену больше нуля.')
        if request.POST.get('manual_queue') == '1' and 'expected_recorded_at' not in request.POST:
            raise ValidationError('Обновите панель перед сохранением цены.')
        return _save_found(request, model, pk, kind, scope, value)
    except (ValueError, TypeError, ValidationError) as exc:
        return JsonResponse({'ok': False, 'message': ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Некорректные данные.'}, status=400)
    except (CD.DoesNotExist, Tech.DoesNotExist):
        return JsonResponse({'ok': False, 'message': 'Товар не найден, выбыл из списка или больше не связан с Avito.'}, status=404)
    except OperationalError:
        return JsonResponse({'ok': False, 'message': 'База занята. Повторите сохранение.'}, status=409)


@retry_database_lock
@transaction.atomic
def _save_found(request, model, pk, kind, scope, value):
    """Цена и аудит атомарны; версия сравнивается только внутри выбранной географии."""
    from integrations.models import AvitoProductProfile
    products = model.objects.select_related('avito_profile').filter(avito_profile__connection__isnull=False)
    if request.POST.get('manual_queue') == '1':
        products = products.annotate(physical_stock=Sum('warehouse_stocks__quantity')).filter(physical_stock__gt=0)
    product = products.get(pk=pk)
    # Блокировка профиля защищает и первое создание цены при отсутствии строки scope.
    # SQLite повторяет целую транзакцию через retry_database_lock, PostgreSQL блокирует строку.
    AvitoProductProfile.objects.select_for_update().get(pk=product.avito_profile.pk)
    previous = AvitoManualPrice.objects.select_for_update().filter(profile=product.avito_profile, scope=scope).first()
    old_price = str(previous.price) if previous else ''
    old_time = previous.recorded_at.isoformat() if previous else ''
    if 'expected_recorded_at' in request.POST and request.POST['expected_recorded_at'] != old_time:
        return JsonResponse({'ok': False, 'message': 'Минимальная цена этой географии уже изменена. Обновите панель и проверьте её снова.'}, status=409)
    now = timezone.now()
    found = previous or AvitoManualPrice(profile=product.avito_profile, scope=scope)
    found.price, found.recorded_at, found.recorded_by = value, now, request.user
    found.full_clean()
    found.save()
    record_product_changes(actor=request.user, instance=product, source=ProductChangeEvent.Source.CRM, changes=[
        {'field_name': 'avito_found_price_' + scope, 'field_label': 'Минимальная цена Avito · ' + SCOPE_LABELS[scope],
         'old_value': old_price, 'new_value': str(value)},
        {'field_name': 'avito_found_price_at_' + scope, 'field_label': 'Дата ручной проверки Avito · ' + SCOPE_LABELS[scope],
         'old_value': old_time, 'new_value': now.isoformat()},
    ])
    prices = {price.scope: price.price for price in AvitoManualPrice.objects.filter(profile=product.avito_profile)}
    warning = WARNING if all(key in prices for key in SCOPES) and prices['russia'] > prices['rostov'] else ''
    return JsonResponse({
        'ok': True, 'kind': kind, 'product_id': pk, 'scope': scope, 'price': format(found.price, '.2f'),
        'recorded_at': timezone.localtime(now).strftime('%d.%m.%Y %H:%M'),
        'recorded_at_version': now.isoformat(), 'warning': warning,
    })


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
