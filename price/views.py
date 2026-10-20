import json
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_all, permission_required_any
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice
from resource_storefront.models import WholesaleContact
from resource_storefront.security import recover_token
from resource_storefront.retail_security import retail_link

from .excel import (
    generate_procurement_customer_xlsx,
    generate_procurement_stock_xlsx,
    generate_retail_price_xlsx,
    generate_supplier_template,
    generate_wholesale_price_xlsx,
    import_supplier_price_files,
)
from .forms import (
    PriceDocumentSettingsForm,
    ProcurementPriceCreateForm,
    ProcurementWeightsForm,
    ProcurementSurchargesForm,
    SupplierPriceUploadForm,
    WarehousePriceForm,
)
from .models import PriceDocumentSettings, ProcurementPriceList, ProcurementPriceListItem
from .services import (
    MissingProcurementWeights, MissingProcurementSurcharges, NegativeProcurementMarkup, create_procurement_price_list,
    get_missing_procurement_weights, get_missing_procurement_surcharges, update_procurement_pricing,
)

logger = logging.getLogger("gamebat.business")


def _price_filename(kind):
    return f"ReSOURCE Price List {kind} {timezone.localdate():%d.%m.%Y}.xlsx"


def _xlsx_response(content, filename):
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = content_disposition_header(True, filename)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@permission_required_any("price.view_price_page")
def price_page(request):
    """Складские прайсы и данные документов — раздел по умолчанию."""
    settings = PriceDocumentSettings.get_solo()
    return render(request, "price/index.html", {
        "settings_form": PriceDocumentSettingsForm(instance=settings),
        "warehouse_form": WarehousePriceForm(),
        "can_change_settings": request.user.is_superuser or request.user.has_perm("price.change_document_settings"),
        "can_generate_retail": request.user.is_superuser or request.user.has_perm("price.generate_retail_price"),
        "can_generate_wholesale": request.user.is_superuser or request.user.has_perm("price.generate_wholesale_price"),
    })


@require_GET
@permission_required_any("price.view_price_page")
def import_prices(request):
    """Прайсы поставщиков и закупочные версии."""
    can_view_supplier = request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    can_view_details = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    can_download_supplier = request.user.is_superuser or request.user.has_perm("price.download_supplier_template")
    suppliers = []
    if can_view_supplier or request.user.is_superuser or request.user.has_perm("price.upload_supplier_price"):
        for supplier in Supplier.objects.order_by("letter", "id"):
            suppliers.append({
                "supplier": supplier,
                "label": supplier.name if can_view_details else supplier.safe_label,
                "cd_price_count": SupplierCDPrice.objects.filter(supplier=supplier, price__gt=0).count() if can_view_supplier else None,
                "tech_price_count": SupplierTechPrice.objects.filter(supplier=supplier, price__gt=0).count() if can_view_supplier else None,
            })
    return render(request, "price/imports.html", {
        "supplier_upload_form": SupplierPriceUploadForm(),
        "procurement_form": ProcurementPriceCreateForm(),
        "suppliers": suppliers,
        "price_lists": ProcurementPriceList.objects.select_related("created_by").prefetch_related("items")[:30],
        "can_download_supplier": can_download_supplier,
        "can_download_supplier_prices": can_download_supplier and can_view_supplier,
        "can_upload_supplier": request.user.is_superuser or request.user.has_perm("price.upload_supplier_price"),
        "can_create_procurement": request.user.is_superuser or request.user.has_perm("price.create_procurement_price_list"),
        "can_export_stock": can_view_supplier and request.user.has_perm("price.export_procurement_price_list"),
    })


@require_GET
@permission_required_any("price.view_price_page")
def site_links(request):
    """Допуски на розничный и оптовый сайты по существующим правам."""
    can_manage_wholesale_contacts = request.user.is_superuser or request.user.has_perm("resource_storefront.manage_wholesale_contacts")
    wholesale_contacts = []
    can_manage_retail = request.user.is_superuser or request.user.has_perm("resource_storefront.manage_retail_storefront")
    retail_config = retail_link(actor=request.user) if can_manage_retail else None
    if can_manage_wholesale_contacts:
        for contact in WholesaleContact.objects.filter(is_archived=False).prefetch_related("access_links"):
            contact.active_link = contact.access_links.filter(is_active=True).first()
            contact.copy_token = recover_token(contact.active_link) if contact.active_link else ""
            wholesale_contacts.append(contact)
    return render(request, "price/site_links.html", {
        "can_manage_wholesale_contacts": can_manage_wholesale_contacts,
        "wholesale_contacts": wholesale_contacts,
        "can_manage_retail": can_manage_retail,
        "retail_token": recover_token(retail_config) if retail_config else "",
    })


@require_POST
@permission_required_any("price.change_document_settings")
def document_settings_update(request):
    instance = PriceDocumentSettings.get_solo()
    form = PriceDocumentSettingsForm(request.POST, request.FILES, instance=instance)
    if form.is_valid():
        form.save()
        messages.success(request, "Данные для прайс-листов сохранены.")
    else:
        messages.error(request, "Проверьте данные шапки прайс-листа.")
    return redirect("price:index")


@require_POST
@permission_required_any("price.generate_retail_price")
def retail_export(request):
    form = WarehousePriceForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Выберите склад для розничного прайса.")
        return redirect("price:index")
    content, skipped = generate_retail_price_xlsx(
        warehouse_id=form.cleaned_data["warehouse"].pk, actor=request.user
    )
    response = _xlsx_response(content, _price_filename("Розница"))
    response["X-ReSOURCE-Skipped-No-Price"] = str(skipped)
    return response


@require_POST
@permission_required_any("price.generate_wholesale_price")
def wholesale_export(request):
    form = WarehousePriceForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Выберите склад для оптового прайса.")
        return redirect("price:index")
    content = generate_wholesale_price_xlsx(
        warehouse_id=form.cleaned_data["warehouse"].pk, actor=request.user
    )
    return _xlsx_response(content, _price_filename("Опт"))


@require_GET
@permission_required_any("price.download_supplier_template")
def supplier_template_export(request, product_kind=None):
    if product_kind is None:
        return redirect("price:imports")
    if product_kind not in ("cd", "tech"):
        raise Http404
    return _xlsx_response(
        generate_supplier_template(actor=request.user, product_kind=product_kind),
        f"resource-supplier-{product_kind}-template.xlsx",
    )


@never_cache
@require_GET
@permission_required_all("price.download_supplier_template", "price.view_supplier_prices")
def supplier_template_prefilled_export(request, supplier_id, product_kind):
    if product_kind not in ("cd", "tech"):
        raise Http404
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    return _xlsx_response(
        generate_supplier_template(
            actor=request.user, product_kind=product_kind, supplier_id=supplier.pk,
        ),
        f"resource-supplier-{supplier.letter}-{product_kind}-template.xlsx",
    )


@require_POST
@permission_required_any("price.upload_supplier_price")
def supplier_price_upload(request):
    form = SupplierPriceUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Выберите поставщика и прайс дисков, техники или оба XLSX-файла.")
        return redirect("price:imports")
    supplier = form.cleaned_data["supplier"]
    try:
        counts = import_supplier_price_files(
            supplier_id=supplier.pk, actor=request.user,
            uploads={kind: form.cleaned_data[f"{kind}_file"] for kind in ("cd", "tech") if form.cleaned_data[f"{kind}_file"]},
        )
    except ValidationError as exc:
        logger.warning(
            "Ошибка импорта прайса поставщика: user_id=%s supplier_id=%s error=%s",
            request.user.pk, supplier.pk, "; ".join(exc.messages),
        )
        messages.error(request, " ".join(exc.messages))
    else:
        labels = {"cd": "Диски", "tech": "Техника"}
        messages.success(request, "Прайсы поставщика обновлены: " + "; ".join(f"{labels[kind]} — {count} цен" for kind, count in counts.items()) + ".")
    return redirect("price:imports")


@require_POST
@permission_required_any("price.create_procurement_price_list")
def procurement_create(request):
    form = ProcurementPriceCreateForm(request.POST)
    valid = form.is_valid()
    preparing = request.POST.get("weights_submitted") == "1" or request.POST.get("surcharges_submitted") == "1"
    missing_weights = get_missing_procurement_weights() if valid or preparing else []
    missing_surcharges = get_missing_procurement_surcharges() if valid or preparing else []
    weights_form = ProcurementWeightsForm(
        request.POST if request.POST.get("weights_submitted") == "1" else None,
        products=missing_weights, user=request.user,
    ) if missing_weights else None
    surcharges_form = ProcurementSurchargesForm(
        request.POST if request.POST.get("surcharges_submitted") == "1" else None,
        products=missing_surcharges, user=request.user,
    ) if missing_surcharges else None
    if not valid or any(extra and (not extra.is_bound or not extra.is_valid()) for extra in (weights_form, surcharges_form)):
        return render(request, "price/procurement_prepare.html", {
            "procurement_form": form, "weights_form": weights_form, "surcharges_form": surcharges_form,
        })
    try:
        price_list = create_procurement_price_list(
            actor=request.user, **form.cleaned_data,
            weights=weights_form.weights if weights_form else None,
            postpayment_surcharges=surcharges_form.surcharges if surcharges_form else None,
        )
    except MissingProcurementWeights as exc:
        form.add_error(None, exc)
        return render(request, "price/procurement_prepare.html", {
            "procurement_form": form,
            "weights_form": ProcurementWeightsForm(request.POST, products=exc.products, user=request.user),
            "surcharges_form": surcharges_form,
        })
    except MissingProcurementSurcharges as exc:
        form.add_error(None, exc)
        return render(request, "price/procurement_prepare.html", {
            "procurement_form": form, "weights_form": weights_form,
            "surcharges_form": ProcurementSurchargesForm(request.POST, products=exc.products, user=request.user),
        })
    except ValidationError as exc:
        form.add_error(None, exc)
        return render(request, "price/procurement_prepare.html", {
            "procurement_form": form, "weights_form": weights_form, "surcharges_form": surcharges_form,
        })
    messages.success(request, f"Закупочный прайс №{price_list.pk} создан.")
    unavailable = getattr(price_list, 'unavailable_products', ())
    if unavailable:
        messages.warning(request, f'Нет доступных предложений для {len(unavailable)} товаров: все их поставщики исключены. Эти товары не включены в новый прайс. ' + '; '.join(p.name for p in unavailable[:5]))
    negative_count = price_list.items.filter(markup_rub__lt=0).count()
    if negative_count:
        messages.warning(request, f"В {negative_count} позициях подставлена сохранённая отрицательная наценка. Проверьте выделенные поля.")
    return redirect("price:procurement_detail", pk=price_list.pk)


@require_GET
@permission_required_any("price.view_price_page")
def procurement_detail(request, pk):
    price_list = get_object_or_404(
        ProcurementPriceList.objects.select_related("created_by").prefetch_related(
            # JOIN внутри выборки строк не создаёт длинную цепочку OR на SQLite.
            Prefetch("items", queryset=ProcurementPriceListItem.objects.select_related(
                "selected_supplier", "cd", "tech",
            )),
        ), pk=pk,
    )
    can_view_supplier_prices = (
        request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    )
    return render(request, "price/procurement_detail.html", {
        "price_list": price_list,
        "can_change_markup": request.user.is_superuser or request.user.has_perm("price.change_procurement_markup"),
        "can_change_delivery": request.user.is_superuser or request.user.has_perm("price.change_procurement_delivery"),
        "can_export": request.user.is_superuser or request.user.has_perm("price.export_procurement_price_list"),
        "can_view_supplier_prices": can_view_supplier_prices,
        "can_view_supplier_details": (
            request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
        ),
    })


@require_POST
@permission_required_any("price.change_procurement_markup", "price.change_procurement_delivery")
def procurement_update(request, pk):
    price_list = get_object_or_404(ProcurementPriceList, pk=pk)
    rows = {}
    try:
        item_ids = list(price_list.items.values_list("id", flat=True))
        if "pricing_rows" in request.POST:
            try:
                payload = json.loads(request.POST["pricing_rows"])
            except (ValueError, RecursionError) as exc:
                raise ValidationError("Не удалось прочитать строки закупочного прайса.") from exc
            if not isinstance(payload, dict) or set(payload) != {str(pk) for pk in item_ids}:
                raise ValidationError("Передан неполный или изменённый состав закупочного прайса.")
            if any(not isinstance(values, dict) for values in payload.values()):
                raise ValidationError("Некорректные данные строки закупочного прайса.")
            rows = {int(item_id): values for item_id, values in payload.items()}
        else:
            for item_id in item_ids:
                rows[item_id] = {
                    "markup": request.POST[f"markup_{item_id}"],
                    "delivery": request.POST[f"delivery_{item_id}"],
                    "price_source": request.POST.get(f"price_source_{item_id}", "markup"),
                    "prepayment": request.POST.get(f"prepayment_{item_id}"),
                    "postpayment": request.POST.get(f"postpayment_{item_id}"),
                }
                if f"surcharge_{item_id}" in request.POST:
                    rows[item_id]["postpayment_surcharge"] = request.POST[f"surcharge_{item_id}"]
                    rows[item_id]["surcharge_mode"] = request.POST.get(f"surcharge_mode_{item_id}", "fixed")
        update_procurement_pricing(
            actor=request.user, price_list_id=pk, rows=rows,
            can_change_markup=request.user.is_superuser or request.user.has_perm("price.change_procurement_markup"),
            can_change_delivery=request.user.is_superuser or request.user.has_perm("price.change_procurement_delivery"),
            negative_markup_confirmed=request.POST.get("negative_markup_confirmed") == "true",
        )
    except NegativeProcurementMarkup as exc:
        return render(request, "price/procurement_confirm.html", {
            "price_list": price_list, "negative_items": exc.items,
            "pricing_rows": json.dumps(rows, ensure_ascii=False),
        })
    except (KeyError, ValidationError) as exc:
        messages.error(
            request,
            " ".join(exc.messages) if isinstance(exc, ValidationError) else "Переданы не все строки прайса.",
        )
    else:
        messages.success(request, "Наценка, доставка и клиентские цены пересчитаны.")
    return redirect("price:procurement_detail", pk=pk)


@require_GET
@permission_required_any("price.export_procurement_price_list")
def procurement_export(request, pk, product_kind=None):
    if product_kind is None:
        return redirect("price:procurement_detail", pk=pk)
    if product_kind not in ("cd", "tech"):
        raise Http404
    content = generate_procurement_customer_xlsx(price_list_id=pk, actor=request.user, product_kind=product_kind)
    return _xlsx_response(content, f"resource-procurement-{pk}-{product_kind}.xlsx")


@require_GET
@permission_required_all("price.export_procurement_price_list", "price.view_supplier_prices")
def procurement_stock_export(request, pk):
    get_object_or_404(ProcurementPriceList, pk=pk)
    return _xlsx_response(generate_procurement_stock_xlsx(price_list_id=pk, actor=request.user),
                          f"resource-stock-procurement-{pk}.xlsx")
