import logging
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import permission_required_any
from warehouse.models import Warehouse, WarehouseTransfer

from .models import CD, Tech
from .nomenclature_forms import CDCardForm, CDCreateForm, TechCardForm, TechCreateForm
from .nomenclature_services import create_product, update_product_card
from .product_filters import filter_product_querysets, product_filter_context

logger = logging.getLogger("gamebat.business")


@permission_required_any("catalog.view_nomenclature")
def nomenclature_list(request):
    filters, filter_context = product_filter_context(request.GET)
    cds = CD.objects.select_related("platform").order_by("platform__name", "name", "id")
    tech_items = Tech.objects.select_related("brand", "product_type").order_by(
        "product_type__name", "name", "id"
    )
    cds, tech_items = filter_product_querysets(cds, tech_items, filters)

    cd_groups = defaultdict(list)
    for product in cds:
        cd_groups[product.platform].append(product)
    tech_groups = defaultdict(list)
    for product in tech_items:
        tech_groups[product.product_type].append(product)
    context = {
        "query": filters.search,
        "cd_groups": list(cd_groups.items()),
        "tech_groups": list(tech_groups.items()),
        "can_add_cd": request.user.is_superuser or request.user.has_perm("catalog.add_cd"),
        "can_add_tech": request.user.is_superuser or request.user.has_perm("catalog.add_tech"),
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
    if request.method == "POST" and form and form.is_valid():
        try:
            product = create_product(
                actor=request.user, product_kind=product_kind, data=form.cleaned_data,
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
        main_fields = ("platform", "name")
        identifier_fields = ("sku", "barcode", "cusa_ppsa_code")
    else:
        main_fields = ("brand", "product_type", "name")
        identifier_fields = ("sku", "barcode")
    return [
        {"title": "Основная информация", "fields": [form[name] for name in main_fields]},
        {"title": "Идентификаторы", "fields": [form[name] for name in identifier_fields]},
        {"title": "Описание и комментарий", "fields": [form[name] for name in ("description", "comment")]},
        {
            "title": "Коммерческая информация",
            "fields": [form[name] for name in ("retail_price", "wholesale_price", "yandex_market_price")],
        },
    ]


def _render_detail(request, *, product, product_kind, form):
    events = product.change_events.select_related("actor").prefetch_related("field_changes")
    event_page = Paginator(events, 10).get_page(request.GET.get("page"))
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
        **_stock_context(product),
    }
    return render(request, "nomenclature/detail.html", context)


def _product_detail(request, *, product_kind, product_id):
    model = CD if product_kind == "cd" else Tech
    form_class = CDCardForm if product_kind == "cd" else TechCardForm
    related_fields = ("platform",) if product_kind == "cd" else ("brand", "product_type")
    product = get_object_or_404(model.objects.select_related(*related_fields), pk=product_id)
    if request.method == "POST":
        try:
            result = update_product_card(
                actor=request.user,
                product_kind=product_kind,
                product_id=product.pk,
                data=request.POST,
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
            form.add_error(None, "Изменения не сохранены. Повторите попытку.")
        else:
            product, form = result.product, result.form
            if result.saved:
                messages.success(request, "Изменения карточки сохранены.")
                return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
            if form.is_valid() and not result.stale:
                messages.info(request, "В карточке нет новых изменений.")
                return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
    else:
        form = form_class(instance=product, user=request.user)
    return _render_detail(
        request,
        product=product,
        product_kind=product_kind,
        form=form,
    )


@permission_required_any("catalog.view_nomenclature")
def cd_detail(request, pk):
    return _product_detail(request, product_kind="cd", product_id=pk)


@permission_required_any("catalog.view_nomenclature")
def tech_detail(request, pk):
    return _product_detail(request, product_kind="tech", product_id=pk)
