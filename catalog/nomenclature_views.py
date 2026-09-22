import logging
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.core.paginator import Paginator
from django.db.models import Exists, IntegerField, OuterRef, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_any
from warehouse.models import Warehouse, WarehouseTransfer

from .models import BarcodeRegistry, CD, Tech
from integrations.models import AvitoListingConnection
from .removal import BLOCK_MESSAGES, remove_product
from .nomenclature_forms import (
    CDCardForm, CDCreateForm, TechCardForm, TechCreateForm, barcode_formset,
)
from .nomenclature_services import create_product, update_product_card
from .product_identifiers import generate_unique_barcode, render_barcode_svg_data_url
from .product_filters import filter_product_querysets, product_filter_context

logger = logging.getLogger("gamebat.business")


@permission_required_any("catalog.view_nomenclature")
def nomenclature_list(request):
    filters, filter_context = product_filter_context(request.GET, include_game_series=True)
    avito_highlight = request.GET.get("avito_highlight", "1") != "0"
    zero_stock_highlight = request.GET.get("zero_stock_highlight", "1") != "0"
    stock_total = Coalesce(Sum("warehouse_stocks__quantity"), Value(0), output_field=IntegerField())
    cds = (
        CD.objects.active()
        .select_related("platform", "game_series")
        .annotate(global_stock=stock_total)
        .order_by("platform__name", "name", "id")
    )
    tech_items = (
        Tech.objects.active()
        .select_related("brand", "product_type")
        .annotate(global_stock=stock_total)
        .order_by("product_type__name", "name", "id")
    )
    if avito_highlight:
        cds = cds.annotate(avito_connected=Exists(
            AvitoListingConnection.objects.filter(profile__cd_id=OuterRef("pk"))
        ))
        tech_items = tech_items.annotate(avito_connected=Exists(
            AvitoListingConnection.objects.filter(profile__tech_id=OuterRef("pk"))
        ))
    cds, tech_items = filter_product_querysets(cds, tech_items, filters)

    platform_products = defaultdict(list)
    for product in cds:
        platform_products[product.platform].append(product)
    cd_groups = []
    for platform, products in platform_products.items():
        series_products = defaultdict(list)
        for product in products:
            series_products[product.game_series].append(product)
        ordered_series = sorted(
            series_products.items(),
            key=lambda group: (group[0] is None, group[0].name.casefold() if group[0] else ""),
        )
        cd_groups.append((platform, {"count": len(products), "series_groups": ordered_series}))
    tech_groups = defaultdict(list)
    for product in tech_items:
        tech_groups[product.product_type].append(product)
    context = {
        "query": filters.search,
        "cd_groups": cd_groups,
        "tech_groups": list(tech_groups.items()),
        "can_add_cd": request.user.is_superuser or request.user.has_perm("catalog.add_cd"),
        "can_add_tech": request.user.is_superuser or request.user.has_perm("catalog.add_tech"),
        "show_game_series_filter": True,
        "show_avito_highlight_toggle": True,
        "avito_highlight": avito_highlight,
        "zero_stock_highlight": zero_stock_highlight,
    }
    context.update(filter_context)
    return render(request, "nomenclature/list.html", context)


@permission_required_any("catalog.add_cd", "catalog.add_tech")
def product_create(request):
    permissions = {
        "cd": request.user.is_superuser or request.user.has_perm("catalog.add_cd"),
        "tech": request.user.is_superuser or request.user.has_perm("catalog.add_tech"),
    }
    product_kind = (request.POST.get("product_kind") or request.GET.get("kind") or "").lower()
    if product_kind and (product_kind not in permissions or not permissions[product_kind]):
        raise PermissionDenied
    form_class = {"cd": CDCreateForm, "tech": TechCreateForm}.get(product_kind)
    form = form_class(request.POST or None) if form_class else None
    barcode_data = None
    if request.method == "POST" and form:
        barcode_data = request.POST
        if "barcodes-TOTAL_FORMS" not in request.POST:
            barcode_data = request.POST.copy()
            legacy_value = str(request.POST.get("barcode") or "").strip()
            barcode_data.update({
                "barcodes-TOTAL_FORMS": "1" if legacy_value else "0",
                "barcodes-INITIAL_FORMS": "0",
                "barcodes-MIN_NUM_FORMS": "0",
                "barcodes-MAX_NUM_FORMS": "1000",
            })
            if legacy_value:
                barcode_data["barcodes-0-value"] = legacy_value
    barcodes = barcode_formset(data=barcode_data) if form else None
    if request.method == "POST" and form and form.is_valid() and barcodes.is_valid():
        try:
            product = create_product(
                actor=request.user, product_kind=product_kind, data=form.cleaned_data,
                barcode_formset_instance=barcodes,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Новое наименование создано.")
            return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
    return render(request, "nomenclature/create.html", {
        "product_kind": product_kind,
        "product_kind_label": "CD" if product_kind == "cd" else "Tech" if product_kind == "tech" else "",
        "form": form,
        "barcode_formset": barcodes,
        "can_add_cd": permissions["cd"],
        "can_add_tech": permissions["tech"],
    })


def _stock_context(product):
    warehouses = list(Warehouse.objects.all())
    quantities = {
        stock.warehouse_id: stock.quantity
        for stock in product.warehouse_stocks.select_related("warehouse")
    }
    active_statuses = (
        WarehouseTransfer.Status.CREATED,
        WarehouseTransfer.Status.ASSEMBLED,
        WarehouseTransfer.Status.SHIPPED,
    )
    transit = product.warehouse_transfer_items.filter(
        transfer__status__in=active_statuses
    ).aggregate(total=Sum("quantity"))["total"] or 0
    warehouse_rows = [
        {"warehouse": warehouse, "quantity": quantities.get(warehouse.pk, 0)}
        for warehouse in warehouses
    ]
    return {
        "warehouse_rows": warehouse_rows,
        "warehouse_total": sum(row["quantity"] for row in warehouse_rows),
        "consignment_total": product.quantity_on_consignment,
        "transit_total": transit,
    }


def _form_sections(form, product_kind):
    if product_kind == "cd":
        main_fields = ("platform", "game_series", "name", "weight_grams")
        identifier_fields = ("sku", "cusa_ppsa_code")
    else:
        main_fields = ("brand", "product_type", "name", "weight_grams")
        identifier_fields = ("sku",)
    return [
        {"title": "Основная информация", "fields": [form[name] for name in main_fields]},
        {"title": "Идентификаторы", "fields": [form[name] for name in identifier_fields]},
        {"title": "Описание и комментарий", "fields": [form[name] for name in ("description", "comment")]},
        {
            "title": "Коммерческая информация",
            "fields": [form[name] for name in ("avito_price", "wholesale_price", "yandex_market_price")],
        },
    ]


def _render_detail(request, *, product, product_kind, form, barcodes=None):
    from integrations.views import product_avito_context

    events = product.change_events.select_related("actor").prefetch_related("field_changes")
    event_page = Paginator(events, 10).get_page(request.GET.get("page"))
    can_change_barcode = request.user.is_superuser or request.user.has_perm(
        f"catalog.change_{product_kind}_barcode"
    )
    context = {
        "product": product,
        "product_kind": product_kind,
        "product_kind_label": "CD" if product_kind == "cd" else "Tech",
        "form": form,
        "form_sections": _form_sections(form, product_kind),
        "warehouse_fields": [
            {
                "stock": form[stock_field_name],
                "storage_location": form[location_field_name],
            }
            for stock_field_name, location_field_name in form.warehouse_field_pairs
        ],
        "event_page": event_page,
        "can_change_barcode": can_change_barcode,
        "barcode_editable": can_change_barcode and not product.is_archived,
        "barcode_formset": barcodes or barcode_formset(product=product),
        **_stock_context(product),
        "can_delete_product": not product.is_archived and (
            request.user.is_superuser or request.user.has_perm(f"catalog.delete_{product_kind}")
        ),
        **(product_avito_context(product, product_kind, request.user) if not product.is_archived else {}),
    }
    return render(request, "nomenclature/detail.html", context)


def _product_detail(request, *, product_kind, product_id):
    model = CD if product_kind == "cd" else Tech
    form_class = CDCardForm if product_kind == "cd" else TechCardForm
    related_fields = ("platform", "game_series") if product_kind == "cd" else ("brand", "product_type")
    product = get_object_or_404(
        model.objects.select_related(*related_fields).prefetch_related("barcodes"), pk=product_id,
    )
    can_change_barcode = request.user.is_superuser or request.user.has_perm(
        f"catalog.change_{product_kind}_barcode"
    )
    if product.is_archived and request.method == "POST":
        raise PermissionDenied("Удалённый товар нельзя изменять.")
    if request.method == "POST":
        try:
            result = update_product_card(
                actor=request.user,
                product_kind=product_kind,
                product_id=product.pk,
                data=request.POST,
                barcode_data=(
                    request.POST if can_change_barcode and "barcodes-TOTAL_FORMS" in request.POST else None
                ),
            )
        except Exception:
            logger.exception(
                "Не удалось изменить карточку товара: user_id=%s type=%s product_id=%s",
                request.user.pk,
                product_kind,
                product.pk,
            )
            product = model.objects.select_related(*related_fields).get(pk=product.pk)
            form = form_class(instance=product, user=request.user)
            barcodes = barcode_formset(product=product)
            form.add_error(None, "Изменения не сохранены. Повторите попытку.")
        else:
            product, form = result.product, result.form
            barcodes = result.barcode_formset or barcode_formset(product=product)
            if result.saved:
                messages.success(request, "Изменения карточки сохранены.")
                return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
            if form.is_valid() and not result.stale and (
                not barcodes.is_bound or barcodes.is_valid()
            ):
                messages.info(request, "В карточке нет новых изменений.")
                return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
    else:
        form = form_class(instance=product, user=request.user)
        barcodes = barcode_formset(product=product)
    return _render_detail(
        request,
        product=product,
        product_kind=product_kind,
        form=form,
        barcodes=barcodes,
    )


@permission_required_any("catalog.view_nomenclature")
def cd_detail(request, pk):
    return _product_detail(request, product_kind="cd", product_id=pk)


@permission_required_any("catalog.view_nomenclature")
def tech_detail(request, pk):
    return _product_detail(request, product_kind="tech", product_id=pk)


@require_POST
@permission_required_any("catalog.view_nomenclature")
def product_delete(request, product_kind, pk):
    if product_kind not in {"cd", "tech"} or not (
        request.user.is_superuser or request.user.has_perm(f"catalog.delete_{product_kind}")
    ):
        raise PermissionDenied
    model = CD if product_kind == "cd" else Tech
    try:
        result = remove_product(product_kind=product_kind, product_id=pk, actor=request.user)
    except model.DoesNotExist as exc:
        raise Http404("Товар не найден.") from exc
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect(f"nomenclature:{product_kind}_detail", pk=pk)
    if result.action == "BLOCKED":
        messages.error(request, " ".join(BLOCK_MESSAGES[reason] for reason in result.reasons))
        return redirect(f"nomenclature:{product_kind}_detail", pk=pk)
    messages.success(request, (
        "Товар удалён." if result.action == "HARD_DELETED"
        else "Товар удалён из активной номенклатуры; история сохранена."
    ))
    return redirect("nomenclature:list")


@require_POST
@permission_required_any("catalog.change_cd_barcode", "catalog.change_tech_barcode")
def barcode_generate(request, product_kind, pk):
    permission = f"catalog.change_{product_kind}_barcode"
    if product_kind not in {"cd", "tech"} or not (
        request.user.is_superuser or request.user.has_perm(permission)
    ):
        raise PermissionDenied
    try:
        product = generate_unique_barcode(
            actor=request.user, product_kind=product_kind, product_id=pk,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Уникальный штрихкод сгенерирован.")
    return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk if 'product' in locals() else pk)


@require_GET
@permission_required_any("catalog.view_nomenclature")
def barcode_print(request, barcode_id):
    barcode_record = get_object_or_404(BarcodeRegistry, pk=barcode_id)
    try:
        barcode_image = render_barcode_svg_data_url(barcode_record.value)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        product = barcode_record.product
        return redirect(f"nomenclature:{product._meta.model_name}_detail", pk=product.pk)
    return render(request, "nomenclature/barcode_print.html", {"barcode_image": barcode_image})


@require_GET
@permission_required_any("catalog.view_nomenclature")
def barcode_print_legacy(request, product_kind, pk):
    model = CD if product_kind == "cd" else Tech if product_kind == "tech" else None
    if model is None:
        raise PermissionDenied
    product = get_object_or_404(model, pk=pk)
    barcode_record = product.barcodes.order_by("id").first()
    if barcode_record is None:
        messages.error(request, "У товара нет штрихкода для печати.")
        return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
    return render(request, "nomenclature/barcode_print.html", {
        "barcode_image": render_barcode_svg_data_url(barcode_record.value),
    })
