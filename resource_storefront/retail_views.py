import hashlib
import uuid

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST
from core.decorators import permission_required_any
from .models import RetailSettings, RetailSubmission
from .retail_security import enter_retail, retail_link
from .modes import storefront_url
from .views import _private
from .forms import RetailCheckoutForm


@require_GET
@sensitive_variables("token")
def access(request, token):
    throttle = "retailer_access:" + hashlib.sha256(request.META.get("REMOTE_ADDR", "unknown").encode()).hexdigest()
    if not cache.add(throttle, 1, timeout=60):
        try:
            count = cache.incr(throttle)
        except ValueError:
            count = 1
        if count > 60:
            return _private(HttpResponse("Слишком много попыток. Повторите позже.", status=429))
    digest = hashlib.sha256(token.encode()).hexdigest()
    config = RetailSettings.objects.filter(pk=1, token_digest=digest).first()
    if not config:
        return _private(render(request, "resource_storefront/unavailable.html", status=404))
    enter_retail(request, config)
    return _private(redirect("retailer:home"))


@require_POST
@permission_required_any("resource_storefront.manage_retail_storefront")
def regenerate(request):
    retail_link(actor=request.user, regenerate=True)
    messages.success(request, "Розничная ссылка обновлена. Старая ссылка и её сеансы закрыты.")
    return redirect("price:index")


def retail_checkout_status(request):
    item = _submission(request)
    if item:
        _clear_cart(request)
    return JsonResponse({"url": storefront_url(request, "success", kwargs={"sale_id":item.sale_id}) if item else None})


def _submission(request):
    visitor = request.session.get("retailer_visitor")
    key = request.session.get("retailer_checkout_key")
    if not visitor or not key:
        return None
    return RetailSubmission.objects.filter(visitor_id=visitor, idempotency_key=key, sale__isnull=False).first()


def _clear_cart(request):
    for key in ("retailer_cart", "retailer_cart_seen", "retailer_checkout_draft"):
        request.session.pop(key, None)


def retail_success(request, sale_id):
    submission = RetailSubmission.objects.select_related("sale").filter(visitor_id=request.session.get("retailer_visitor"), sale_id=sale_id).first()
    if not submission:
        raise Http404
    return render(request, "resource_storefront/success.html", {"sale":submission.sale, "cart_count":0})


def retail_checkout(request):
    from .views import _ajax, _cart_context
    from .catalogue import parse_cart
    from sales.models import Sale
    from sales.services import create_sale, _locked_inventory
    from warehouse.models import Warehouse

    draft = {name: request.POST.get(name, "")[:5000 if name == "comment" else 160]
             for name in ("name", "phone", "telegram", "whatsapp", "comment")}
    draft["communication"] = request.POST.getlist("communication")[:3]
    draft["telegram_use_phone"] = request.POST.get("telegram_use_phone") == "on"
    request.session["retailer_checkout_draft"] = draft
    form = RetailCheckoutForm(request.POST)
    if not form.is_valid():
        if _ajax(request):
            return JsonResponse({"error":"Проверьте контактные данные.","fields":form.errors},status=400)
        context = _cart_context(request)
        context["checkout_form"] = form
        return render(request, "resource_storefront/cart.html", context, status=400)

    def success(sale_id):
        _clear_cart(request)
        url = storefront_url(request, "success", kwargs={"sale_id":sale_id})
        return JsonResponse({"url":url}) if _ajax(request) else redirect(url)

    def error(message, status=409, refresh=True):
        if _ajax(request):
            return JsonResponse({"error":message,"refresh":refresh},status=status)
        messages.error(request,message)
        return redirect("retailer:cart")

    visitor = request.session.get("retailer_visitor")
    key = request.session.get("retailer_checkout_key")
    if not visitor or not key:
        return error("Откройте корзину и проверьте состав заказа.")
    payment_method = Sale.PaymentMethod.UNDEFINED
    try:
        with transaction.atomic():
            config = RetailSettings.objects.select_for_update().filter(pk=1,generation=request.session.get("retailer_generation")).first()
            if not config or not config.warehouse_id:
                return error("Доступ изменился. Откройте действующую розничную ссылку.",status=403,refresh=False)
            previous = RetailSubmission.objects.filter(visitor_id=visitor,idempotency_key=key).first()
            if previous and previous.sale_id:
                return success(previous.sale_id)
            Warehouse.objects.select_for_update().get(pk=config.warehouse_id)
            cart = parse_cart(request.session,"retail")
            lines = [{"product_type":k.split(":")[0],"product_id":int(k.split(":")[1]),"quantity":v} for k,v in cart.items()]
            # Те же блокировки, что у CRM/опта: после них ещё раз сравниваются цены и остатки.
            _locked_inventory(config.warehouse_id, lines)
            context = _cart_context(request)
            if not context["checkout_allowed"] or request.POST.get("cart_version") != context["version"]:
                return error("Цена или наличие изменились. Обновите корзину и подтвердите актуальный состав.")
            submission = RetailSubmission.objects.create(visitor_id=visitor,idempotency_key=key,cart_digest=context["version"])
            sale = create_sale(actor=None, warehouse_id=config.warehouse_id, price_type=Sale.PriceType.RETAIL,
                               sale_type=Sale.SaleType.RETAIL, payment_method=payment_method, lines=lines)
            sale.storefront_source = "resource_retail"
            sale.buyer_name_snapshot = form.cleaned_data["name"]
            sale.buyer_phone_snapshot = form.cleaned_data["phone"]
            sale.buyer_contact_methods = form.cleaned_data["communication"]
            sale.buyer_telegram = form.cleaned_data["telegram"]
            sale.buyer_whatsapp = form.cleaned_data["whatsapp"]
            sale.buyer_comment = form.cleaned_data["comment"]
            sale.save(update_fields=("storefront_source","buyer_name_snapshot","buyer_phone_snapshot","buyer_contact_methods","buyer_telegram","buyer_whatsapp","buyer_comment","updated_at"))
            submission.sale = sale
            submission.save(update_fields=("sale",))
    except IntegrityError:
        previous = _submission(request)
        if previous:
            return success(previous.sale_id)
        return error("Заказ не оформлен. Проверьте актуальный состав корзины.")
    except ValidationError as exc:
        return error(" ".join(exc.messages))
    return success(sale.pk)
