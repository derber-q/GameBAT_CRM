import logging
import mimetypes
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, QueryDict
from django.core.paginator import Paginator
from django.db.models import Exists, IntegerField, OuterRef, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_any
from warehouse.models import Warehouse, WarehouseTransfer

from .models import BarcodeRegistry, CD, ProductImage, Tech
from integrations.models import AvitoListingConnection
from .removal import BLOCK_MESSAGES, remove_product, remove_products
from .nomenclature_forms import (
    BulkProductDeleteForm, CDCardForm, CDCreateForm, TechCardForm, TechCreateForm, barcode_formset,
)
from .nomenclature_services import create_product, update_product_card
from .product_media import (
    add_gallery_images,
    delete_gallery_image,
    delete_title_image,
    product_model,
    set_title_image,
)
from .product_identifiers import generate_unique_barcode, render_barcode_svg_data_url
from .product_filters import filter_product_querysets, product_filter_context
from .product_ordering import cd_order_key, tech_brand_groups

logger = logging.getLogger("gamebat.business")

NOMENCLATURE_LIST_ROUTES = {
    "": "nomenclature:list",
    "cd": "nomenclature:cd_list",
    "tech": "nomenclature:tech_list",
}


@permission_required_any("catalog.view_nomenclature")
def nomenclature_list(request, product_kind=None):
    if product_kind not in {None, "cd", "tech"}:
        raise Http404("Раздел номенклатуры не найден.")
    params = request.GET.copy()
    # Тип задаётся маршрутом; чужие фильтры в URL не меняют выбранный раздел.
    irrelevant_filters = (
        ("platform", "game_series") if product_kind == "tech"
        else ("brand", "product_type") if product_kind == "cd" else ()
    )
    for key in irrelevant_filters:
        params.pop(key, None)
    filters, filter_context = product_filter_context(params, include_game_series=product_kind != "tech")
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
    if product_kind == "cd":
        tech_items = tech_items.none()
    elif product_kind == "tech":
        cds = cds.none()
    if avito_highlight:
        cds = cds.annotate(avito_connected=Exists(
            AvitoListingConnection.objects.filter(profile__cd_id=OuterRef("pk"))
        ))
        tech_items = tech_items.annotate(avito_connected=Exists(
            AvitoListingConnection.objects.filter(profile__tech_id=OuterRef("pk"))
        ))
    cds, tech_items = filter_product_querysets(cds, tech_items, filters)

    platform_products = defaultdict(list)
    for product in sorted(cds, key=cd_order_key):
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
    can_delete_cd = product_kind != "tech" and (
        request.user.is_superuser or request.user.has_perm("catalog.delete_cd")
    )
    can_delete_tech = product_kind != "cd" and (
        request.user.is_superuser or request.user.has_perm("catalog.delete_tech")
    )
    context = {
        "nomenclature_kind": product_kind or "",
        "nomenclature_title": {None: "Номенклатура", "cd": "Диски", "tech": "Техника"}[product_kind],
        "query": filters.search,
        "cd_groups": cd_groups,
        "tech_groups": list(tech_groups.items()),
        "tech_brand_groups": tech_brand_groups([product for products in tech_groups.values() for product in products]),
        "can_add_cd": product_kind != "tech" and (
            request.user.is_superuser or request.user.has_perm("catalog.add_cd")
        ),
        "can_add_tech": product_kind != "cd" and (
            request.user.is_superuser or request.user.has_perm("catalog.add_tech")
        ),
        "can_delete_cd": can_delete_cd,
        "can_delete_tech": can_delete_tech,
        "can_bulk_delete": can_delete_cd or can_delete_tech,
        "bulk_delete_result": request.session.pop("nomenclature_bulk_delete_result", None),
        "show_game_series_filter": product_kind != "tech",
        "hide_cd_filters": product_kind == "tech",
        "hide_tech_filters": product_kind == "cd",
        "show_avito_highlight_toggle": True,
        "avito_highlight": avito_highlight,
        "zero_stock_highlight": zero_stock_highlight,
    }
    context.update(filter_context)
    return render(request, "nomenclature/list.html", context)


@require_POST
@permission_required_any("catalog.view_nomenclature")
@permission_required_any("catalog.delete_cd", "catalog.delete_tech")
def product_bulk_delete(request):
    form = BulkProductDeleteForm(request.POST)
    query = ""
    if not form.is_valid():
        messages.error(request, "Удаление не выполнено. " + " ".join(
            str(error) for errors in form.errors.values() for error in errors
        ))
    else:
        # Разбираем параметры до удаления: некорректные фильтры не должны давать ошибку после записи.
        query = QueryDict(form.cleaned_data["query"]).urlencode()
        results = remove_products(selection=form.cleaned_data["selection"], actor=request.user)
        request.session["nomenclature_bulk_delete_result"] = {
            "selected": len(results),
            "deleted": sum(item.action == "HARD_DELETED" for item in results),
            "archived": sum(item.action == "ARCHIVED" for item in results),
            "blocked": [
                {
                    "kind": item.product_kind,
                    "id": item.product_id,
                    "name": item.product_name,
                    "reason": " ".join(item.messages),
                }
                for item in results if item.action == "BLOCKED"
            ],
        }
    # Возвращаемся к тем же фильтрам; адрес перенаправления всегда локальный.
    list_kind = form.cleaned_data.get("list_kind", "")
    url = reverse(NOMENCLATURE_LIST_ROUTES.get(list_kind, "nomenclature:list"))
    return redirect(f"{url}?{query}" if query else url)


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
        main_fields = ("platform", "game_series", "name")
        identifier_fields = ("sku", "cusa_ppsa_code")
    else:
        main_fields = ("brand", "product_type", "name")
        identifier_fields = ("sku",)
    return [
        {"title": "Основная информация", "fields": [form[name] for name in main_fields]},
        {"title": "Идентификаторы", "fields": [form[name] for name in identifier_fields]},
        {"title": "Габариты для маркетплейсов", "fields": [form[name] for name in ("length_cm", "width_cm", "height_cm", "weight_grams")]},
        {"title": "Описание и комментарий", "fields": [form[name] for name in ("description", "comment")]},
        {
            "title": "Коммерческая информация",
            "fields": [form[name] for name in (
                "avito_price", "avito_markup_from_wholesale",
                "yandex_market_price", "yandex_markup_from_wholesale", "wholesale_price",
                "yandex_desired_profit", "yandex_pricing_integration", "yandex_pricing_category",
            )],
        },
        {
            "title": "Прайсы поставщиков",
            "fields": [form["exclude_from_supplier_template"]],
        },
    ]


def _render_detail(request, *, product, product_kind, form, barcodes=None):
    from integrations.views import product_avito_context
    from yandex_market.models import Integration

    events = product.change_events.select_related("actor").prefetch_related("field_changes")
    event_page = Paginator(events, 10).get_page(request.GET.get("page"))
    can_change_barcode = request.user.is_superuser or request.user.has_perm(
        f"catalog.change_{product_kind}_barcode"
    )
    can_change_media = not product.is_archived and (
        request.user.is_superuser
        or request.user.has_perm(f"catalog.change_{product_kind}_media")
    )
    gallery_images = list(product.catalog_images.all())
    context = {
        "product": product,
        "yandex_links": product.yandex_connections.filter(active=True).select_related("remote_offer") if request.user.has_perm("yandex_market.view_integration") else [],
        "yandex_integrations": Integration.objects.all() if request.user.has_perm("yandex_market.bind_offer") else [],
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
        "can_change_media": can_change_media,
        "additional_images": [
            image for image in gallery_images
            if image.image_kind == ProductImage.ImageKind.ADDITIONAL
        ],
        "product_images": [
            image for image in gallery_images
            if image.image_kind == ProductImage.ImageKind.PRODUCT
        ],
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
        model.objects.select_related(*related_fields).prefetch_related("barcodes", "catalog_images"),
        pk=product_id,
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


def _can_view_product_media(user):
    permissions = (
        "catalog.view_nomenclature",
        "catalog.view_cd",
        "catalog.view_tech",
        "warehouse.view_global_stock",
        "warehouse.view_warehouse_stock",
        "pricing.view_pricing",
    )
    return user.is_authenticated and (
        user.is_superuser or any(user.has_perm(permission) for permission in permissions)
    )


def _require_media_change(request, product_kind):
    if product_kind not in {"cd", "tech"} or not (
        request.user.is_superuser
        or request.user.has_perm(f"catalog.change_{product_kind}_media")
    ):
        raise PermissionDenied("У вас нет права изменять изображения этого товара.")


def _media_response(field_file):
    try:
        handle = field_file.open("rb")
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise Http404("Изображение не найдено.") from exc
    content_type = mimetypes.guess_type(field_file.name)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type)
    response["Cache-Control"] = "private, no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
def product_title_image(request, product_kind, pk):
    if not _can_view_product_media(request.user):
        raise PermissionDenied("У вас нет доступа к изображениям товаров.")
    try:
        model = product_model(product_kind)
    except ValidationError as exc:
        raise Http404("Товар не найден.") from exc
    product = get_object_or_404(model, pk=pk)
    if not product.title_image:
        raise Http404("Титульное фото не загружено.")
    return _media_response(product.title_image)


@require_GET
def product_gallery_image(request, product_kind, pk, image_id):
    if not _can_view_product_media(request.user):
        raise PermissionDenied("У вас нет доступа к изображениям товаров.")
    try:
        product_model(product_kind)
    except ValidationError as exc:
        raise Http404("Изображение не найдено.") from exc
    relation_filter = {"cd_id": pk} if product_kind == "cd" else {"tech_id": pk}
    image = get_object_or_404(
        ProductImage,
        pk=image_id,
        product_kind=product_kind,
        **relation_filter,
    )
    return _media_response(image.image)


@require_POST
@permission_required_any("catalog.view_nomenclature")
def product_title_upload(request, product_kind, pk):
    _require_media_change(request, product_kind)
    try:
        set_title_image(
            actor=request.user,
            product_kind=product_kind,
            product_id=pk,
            upload=request.FILES.get("image"),
        )
    except (CD.DoesNotExist, Tech.DoesNotExist):
        raise Http404("Товар не найден.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Титульное фото сохранено.")
    return redirect(f"nomenclature:{product_kind}_detail", pk=pk)


@require_POST
@permission_required_any("catalog.view_nomenclature")
def product_title_delete(request, product_kind, pk):
    _require_media_change(request, product_kind)
    try:
        delete_title_image(
            actor=request.user, product_kind=product_kind, product_id=pk,
        )
    except (CD.DoesNotExist, Tech.DoesNotExist):
        raise Http404("Товар не найден.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Титульное фото удалено.")
    return redirect(f"nomenclature:{product_kind}_detail", pk=pk)


@require_POST
@permission_required_any("catalog.view_nomenclature")
def product_gallery_upload(request, product_kind, pk):
    _require_media_change(request, product_kind)
    try:
        created = add_gallery_images(
            actor=request.user,
            product_kind=product_kind,
            product_id=pk,
            image_kind=request.POST.get("image_kind", ""),
            uploads=request.FILES.getlist("images"),
        )
    except (CD.DoesNotExist, Tech.DoesNotExist):
        raise Http404("Товар не найден.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"Добавлено изображений: {len(created)}.")
    return redirect(f"nomenclature:{product_kind}_detail", pk=pk)


@require_POST
@permission_required_any("catalog.view_nomenclature")
def product_gallery_delete(request, product_kind, pk, image_id):
    _require_media_change(request, product_kind)
    try:
        delete_gallery_image(
            actor=request.user,
            product_kind=product_kind,
            product_id=pk,
            image_id=image_id,
        )
    except (CD.DoesNotExist, Tech.DoesNotExist, ProductImage.DoesNotExist):
        raise Http404("Изображение не найдено.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Изображение удалено.")
    return redirect(f"nomenclature:{product_kind}_detail", pk=pk)


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
