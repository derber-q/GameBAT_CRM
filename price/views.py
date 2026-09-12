import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_any
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice

from .excel import (
    generate_procurement_customer_xlsx,
    generate_retail_price_xlsx,
    generate_supplier_template,
    generate_wholesale_price_xlsx,
    import_supplier_price,
)
from .forms import (
    PriceDocumentSettingsForm,
    ProcurementPriceCreateForm,
    SupplierPriceUploadForm,
    WarehousePriceForm,
)
from .models import PriceDocumentSettings, ProcurementPriceList
from .services import create_procurement_price_list, update_procurement_pricing

logger = logging.getLogger("gamebat.business")


def _xlsx_response(content, filename):
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
@permission_required_any("price.view_price_page")
def price_page(request):
    settings = PriceDocumentSettings.get_solo()
    can_view_supplier = request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    can_view_details = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    suppliers = []
    if can_view_supplier or request.user.is_superuser or request.user.has_perm("price.upload_supplier_price"):
        for supplier in Supplier.objects.order_by("letter", "id"):
            suppliers.append({
                "supplier": supplier,
                "label": supplier.name if can_view_details else supplier.safe_label,
                "price_count": (
                    SupplierCDPrice.objects.filter(supplier=supplier, price__gt=0).count()
                    + SupplierTechPrice.objects.filter(supplier=supplier, price__gt=0).count()
                ) if can_view_supplier else None,
            })
    return render(request, "price/index.html", {
        "settings_form": PriceDocumentSettingsForm(instance=settings),
        "warehouse_form": WarehousePriceForm(),
        "supplier_upload_form": SupplierPriceUploadForm(),
        "procurement_form": ProcurementPriceCreateForm(),
        "suppliers": suppliers,
        "price_lists": ProcurementPriceList.objects.select_related("created_by").prefetch_related("items")[:30],
        "can_change_settings": request.user.is_superuser or request.user.has_perm("price.change_document_settings"),
        "can_generate_retail": request.user.is_superuser or request.user.has_perm("price.generate_retail_price"),
        "can_generate_wholesale": request.user.is_superuser or request.user.has_perm("price.generate_wholesale_price"),
        "can_download_supplier": request.user.is_superuser or request.user.has_perm("price.download_supplier_template"),
        "can_upload_supplier": request.user.is_superuser or request.user.has_perm("price.upload_supplier_price"),
        "can_create_procurement": request.user.is_superuser or request.user.has_perm("price.create_procurement_price_list"),
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
    response = _xlsx_response(content, "resource-retail-price.xlsx")
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
    return _xlsx_response(content, "resource-wholesale-price.xlsx")


@require_GET
@permission_required_any("price.download_supplier_template")
def supplier_template_export(request):
    return _xlsx_response(generate_supplier_template(actor=request.user), "resource-supplier-template.xlsx")


@require_POST
@permission_required_any("price.upload_supplier_price")
def supplier_price_upload(request):
    form = SupplierPriceUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Выберите поставщика и корректный XLSX-файл.")
        return redirect("price:index")
    supplier = form.cleaned_data["supplier"]
    try:
        count = import_supplier_price(supplier_id=supplier.pk, upload=form.cleaned_data["file"], actor=request.user)
    except ValidationError as exc:
        logger.warning(
            "Ошибка импорта прайса поставщика: user_id=%s supplier_id=%s error=%s",
            request.user.pk, supplier.pk, "; ".join(exc.messages),
        )
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, f"Прайс поставщика заменён: {count} актуальных цен.")
    return redirect("price:index")


@require_POST
@permission_required_any("price.create_procurement_price_list")
def procurement_create(request):
    form = ProcurementPriceCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Укажите положительный курс AED → RUB.")
        return redirect("price:index")
    try:
        price_list = create_procurement_price_list(
            actor=request.user, exchange_rate=form.cleaned_data["exchange_rate"]
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("price:index")
    messages.success(request, f"Закупочный прайс №{price_list.pk} создан.")
    return redirect("price:procurement_detail", pk=price_list.pk)


@require_GET
@permission_required_any("price.view_price_page")
def procurement_detail(request, pk):
    price_list = get_object_or_404(
        ProcurementPriceList.objects.select_related("created_by").prefetch_related(
            "items__selected_supplier", "items__cd", "items__tech"
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
        for item_id in price_list.items.values_list("id", flat=True):
            rows[item_id] = {
                "markup": request.POST[f"markup_{item_id}"],
                "delivery": request.POST[f"delivery_{item_id}"],
            }
        update_procurement_pricing(
            actor=request.user, price_list_id=pk, rows=rows,
            can_change_markup=request.user.is_superuser or request.user.has_perm("price.change_procurement_markup"),
            can_change_delivery=request.user.is_superuser or request.user.has_perm("price.change_procurement_delivery"),
        )
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
def procurement_export(request, pk):
    content = generate_procurement_customer_xlsx(price_list_id=pk, actor=request.user)
    return _xlsx_response(content, f"resource-procurement-{pk}.xlsx")
