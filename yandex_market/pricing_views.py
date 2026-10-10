"""Настройки тарифов FBS и заполнение только отсутствующих характеристик."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .fbs_pricing import pricing_configuration
from .models import CategorySchema, Integration, RemoteOffer
from .pricing_forms import CategoryRateFormSet, FBSSettingsForm, MiddleMileFormSet, category_rates_initial, clean_configuration
from .services import audit
from .views import access


@access("manage_settings")
def settings_view(request, pk):
    integration = get_object_or_404(Integration, pk=pk)
    initial_rates = {row["category_id"]: row for row in category_rates_initial()}
    for row in RemoteOffer.objects.filter(integration=integration, category_id__isnull=False).values("category_id", "category_name"):
        initial_rates.setdefault(row["category_id"], {"category_id": row["category_id"], "name": row["category_name"], "placement_rate": None})
    data = request.POST if request.method == "POST" and request.POST.get("action") != "fill_dimensions" else None
    form = FBSSettingsForm(data, integration=integration)
    bands = MiddleMileFormSet(data, prefix="bands", initial=pricing_configuration(integration)["middle_bands"])
    rates = CategoryRateFormSet(data, prefix="rates", initial=list(initial_rates.values()))
    if request.method == "POST" and request.POST.get("action") == "fill_dimensions":
        from .product_dimensions import fill_integration_dimensions
        count = fill_integration_dimensions(integration, actor=request.user)
        messages.success(request, f"Габариты дополнены у {count} товаров по сохранённым данным Маркета. Для актуализации исходных данных используйте обычное обновление каталога.")
        return redirect("yandex_market:pricing_settings", pk=pk)
    if data is not None:
        configuration = clean_configuration(form, bands)
        if rates.is_valid() and configuration is not None:
            rows = [row for row in rates.cleaned_data if row]
            if len({row["category_id"] for row in rows}) != len(rows):
                form.add_error(None, "ID категории повторяется в таблице тарифов.")
            else:
                with transaction.atomic():
                    locked = Integration.objects.select_for_update().get(pk=pk)
                    locked.configuration = {**locked.configuration, "fbs_pricing": configuration}
                    locked.save(update_fields=["configuration"])
                    for row in rows:
                        category, _ = CategorySchema.objects.get_or_create(category_id=row["category_id"])
                        category.name = row["name"]
                        category.placement_rate = row["placement_rate"]
                        category.full_clean(exclude=["schema"])
                        category.save(update_fields=["name", "placement_rate"])
                    audit(locked, request.user, "fbs_pricing_settings", pk, fields=list(configuration), categories=[row["category_id"] for row in rows])
                messages.success(request, "Тарифы FBS сохранены. Рассчитанные цены обновлены; отправляемые цены не изменены.")
                return redirect("yandex_market:pricing_settings", pk=pk)
    return render(request, "yandex_market/pricing_settings.html", {"integration": integration, "form": form, "bands": bands, "rates": rates})
