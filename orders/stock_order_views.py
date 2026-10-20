from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from core.decorators import permission_required_all
from price.models import ProcurementPriceList

from .models import CustomerProcurementOrder
from .stock_order_form import StockOrderCreateForm, StockOrderPriceListForm, stock_order_groups, stock_order_items
from .views import DRAFT_SESSION_KEY


@never_cache
@require_http_methods(["GET", "POST"])
@permission_required_all("orders.create_order", "price.view_supplier_prices")
def stock_order_create(request):
    latest = ProcurementPriceList.objects.first()
    selected_id = (request.POST.get("price_list") if request.method == "POST"
                   else request.GET.get("price_list", latest.pk if latest else ""))
    choice_form = StockOrderPriceListForm({"price_list": selected_id})
    price_list, form, groups = None, None, []
    if latest and choice_form.is_valid():
        price_list = choice_form.cleaned_data["price_list"]
        items = stock_order_items(price_list)
        draft = request.session.get(DRAFT_SESSION_KEY, {})
        initial = {}
        if draft.get("entry_method") == "form" and draft.get("price_list_id") == price_list.pk:
            initial = {"recipient": draft["recipient"], "comment": draft["comment"], **{
                f"quantity_{row['price_list_item_id']}": row["prepayment_quantity"] for row in draft["lines"]
            }}
        form = StockOrderCreateForm(request.POST if request.method == "POST" else None, items=items, initial=initial)
        if request.method == "POST" and form.is_valid():
            request.session[DRAFT_SESSION_KEY] = {
                "price_list_id": price_list.pk, "recipient": form.cleaned_data["recipient"],
                "comment": form.cleaned_data["comment"], "lines": form.order_lines(),
                "purpose": CustomerProcurementOrder.Purpose.STOCK, "entry_method": "form",
            }
            return redirect("orders:preview")
        groups = stock_order_groups(items, form)
    return render(request, "orders/stock_create.html", {
        "choice_form": choice_form, "form": form, "price_list": price_list,
        "groups": groups, "has_price_lists": latest is not None,
    })
