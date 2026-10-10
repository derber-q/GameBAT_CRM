import hashlib
import json
import mimetypes
import re
from io import BytesIO
from decimal import Decimal
from uuid import uuid4

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from catalog.models import CD, Tech, ProductImage
from catalog.audit import field_change, record_product_changes
from catalog.models import ProductChangeEvent
from core.decorators import permission_required_any
from sales.models import Sale
from sales.services import create_sale
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .catalogue import buyer_filters, parse_cart, product_by_id, product_images, row_key, set_cart, visible_product_rows
from .models import (
    CollectionProduct, NewsCDProduct, NewsTechProduct, ProductCollection, StorefrontNews,
    StorefrontProduct, StorefrontSettings, StorefrontSubmission, WholesaleAccessLink, WholesaleContact,
)
from .security import enter_buyer_session, issue_link, recover_token, validate_buyer
from .filters import CATEGORY_CHOICES, CatalogueFilterForm, normalized_query
from .forms import CheckoutForm, RetailCheckoutForm
from .modes import mode_for, session_key, storefront_url, config_for


def _ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _private(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Referrer-Policy"] = "no-referrer"
    return response


def buyer_required(view):
    def wrapped(request, *args, **kwargs):
        if mode_for(request) == "retail":
            from .retail_security import validate_retail
            if not validate_retail(request):
                if _ajax(request):
                    return _private(JsonResponse({"error": "Доступ закрыт. Откройте действующую розничную ссылку."}, status=403))
                return _private(render(request, "resource_storefront/unavailable.html", status=403))
            request.wholesale_contact = None
            return _private(view(request, *args, **kwargs))
        contact = validate_buyer(request)
        if not contact:
            staff_preview = (
                request.method == "GET"
                and request.session.get("resource_staff_preview")
                and request.user.is_authenticated
                and (request.user.is_superuser or request.user.has_perm("resource_storefront.manage_storefront"))
                and view.__name__ in {"home", "catalogue", "product_detail", "news_list", "news_detail", "product_photo", "content_asset"}
            )
            if not staff_preview:
                if _ajax(request):
                    return _private(JsonResponse({"error": "Доступ закрыт. Откройте действующую персональную ссылку."}, status=403))
                return _private(redirect("resource_storefront:denied"))
            request.storefront_preview = True
        request.wholesale_contact = contact
        return _private(view(request, *args, **kwargs))
    wrapped.__name__ = view.__name__
    return wrapped


@require_GET
@never_cache
def denied(request):
    return _private(render(request, "resource_storefront/unavailable.html", status=403))


@require_GET
@never_cache
def access(request, token):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    throttle_key = "resource_access:" + hashlib.sha256(ip.encode("utf-8")).hexdigest()
    if not cache.add(throttle_key, 1, timeout=60):
        try:
            attempts = cache.incr(throttle_key)
        except ValueError:
            cache.set(throttle_key, 2, timeout=60)
            attempts = 2
        if attempts > 40:
            return _private(HttpResponse("Too many attempts", status=429))
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    link = WholesaleAccessLink.objects.select_related("contact").filter(
        token_digest=digest, is_active=True, contact__is_archived=False,
    ).first()
    if not link:
        return _private(render(request, "resource_storefront/unavailable.html", status=404))
    enter_buyer_session(request, link)
    response = redirect("resource_storefront:home")
    return _private(response)


def _row_for_slot(slot):
    kind = "cd" if slot.cd_id else "tech"
    return product_by_id(kind, slot.cd_id or slot.tech_id)


@buyer_required
@require_GET
def home(request):
    settings_obj = StorefrontSettings.objects.filter(pk=1).first()
    new_rows = [_row_for_slot(slot) for slot in StorefrontProduct.objects.filter(placement="new")]
    featured_rows = [_row_for_slot(slot) for slot in StorefrontProduct.objects.filter(placement="home")]
    collections = []
    for collection in ProductCollection.objects.filter(is_visible=True):
        rows = [_row_for_slot(item) for item in collection.items.select_related("cd", "tech")]
        rows = [row for row in rows if row]
        if rows:
            collections.append({"collection": collection, "rows": rows})
    if getattr(request, "storefront_preview", False) and request.GET.get("preview") == "drafts":
        news = StorefrontNews.objects.filter(Q(status="published", published_at__lte=timezone.now()) | Q(status="draft"))[:6]
    else:
        news = StorefrontNews.objects.filter(status="published", published_at__lte=timezone.now())[:3]
    category_rows = [{"label": label, "url": reverse("resource_storefront:catalogue") + f"?category={key}",
                      "image": f"resource/artwork/category-{key}.webp"}
                     for key, label in CATEGORY_CHOICES if key in {"cd", "consoles", "gamepads", "accessories"}]
    response = render(request, "resource_storefront/home.html", {
        "settings": settings_obj, "new_rows": [row for row in new_rows if row],
        "featured_rows": [row for row in featured_rows if row], "collections": collections,
        "news": news, "categories": category_rows, "cart_count": sum(parse_cart(request.session).values()),
        "can_manage_storefront": request.user.is_authenticated and request.user.has_perm("resource_storefront.manage_storefront"),
        "storefront_preview": getattr(request, "storefront_preview", False) and request.GET.get("preview") == "drafts",
    })
    return response


@buyer_required
@require_GET
def catalogue(request, kind=None):
    data = normalized_query(request.GET)
    ids = None
    if kind == "new":
        ids = {"cd": list(StorefrontProduct.objects.filter(placement="new", cd__isnull=False).values_list("cd_id", flat=True)),
               "tech": list(StorefrontProduct.objects.filter(placement="new", tech__isnull=False).values_list("tech_id", flat=True))}
    filters = buyer_filters(visible_product_rows(ids=ids, mode=mode_for(request)))
    form = CatalogueFilterForm(data, filters=filters)
    if mode_for(request) == "retail":
        form.fields["sort"].choices = [choice for choice in form.fields["sort"].choices if choice[0] != "newest"]
    rows = []
    if form.is_valid():
        cleaned = form.cleaned_data
        rows = visible_product_rows(category=cleaned["category"], query=cleaned["q"],
            platform=cleaned["platform"], brand=cleaned["brand"], product_type=cleaned["product_type"],
            price_min=cleaned["price_min"], price_max=cleaned["price_max"], ordering=cleaned["sort"], ids=ids, mode=mode_for(request))
        # После смены раздела несовместимые параметры исчезают и из URL.
        if request.GET.get("kind") or any(request.GET.get(key, "") != data[key] for key in ("category", "platform", "brand", "product_type")):
            return redirect(request.path + "?" + data.urlencode())
    page = Paginator(rows, 12).get_page(request.GET.get("page", 1))
    pagination = []
    def page_url(number):
        params = data.copy()
        params["page"] = number
        return "?" + params.urlencode()
    for number in page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1):
        pagination.append({"number": number, "url": page_url(number), "ellipsis": number == page.paginator.ELLIPSIS})
    return render(request, "resource_storefront/catalogue.html", {
        "page_obj": page, "filters": filters, "filter_form": form, "pagination": pagination,
        "cart_count": sum(parse_cart(request.session, mode_for(request)).values()), "query": data,
        "search_state": [(key, value) for key, value in data.items() if key != "q" and value],
        "show_platform": data["category"] in {"", "cd"}, "show_tech": data["category"] != "cd",
        "previous_url": page_url(page.previous_page_number()) if page.has_previous() else "",
        "next_url": page_url(page.next_page_number()) if page.has_next() else "",
        "active_filters": [(form.fields[key].label, dict(form.fields[key].choices).get(value, value) if hasattr(form.fields[key], "choices") else value)
                           for key, value in data.items() if value and key not in {"sort"}],
    })


@buyer_required
@require_GET
def product_detail(request, kind, pk):
    row = product_by_id(kind, pk, mode_for(request))
    if not row:
        return render(request, "resource_storefront/unavailable.html", {"cart_count": sum(parse_cart(request.session, mode_for(request)).values())}, status=404)
    back_url = request.GET.get("back", "")
    if not back_url.startswith(("/retailer/",) if mode_for(request) == "retail" else ("/opt/catalog/", "/opt/new/")) or not url_has_allowed_host_and_scheme(back_url, {request.get_host()}):
        back_url = storefront_url(request, "catalogue")
    return render(request, "resource_storefront/product.html", {
        "row": row, "images": product_images(row), "cart_count": sum(parse_cart(request.session, mode_for(request)).values()),
        "back_url": back_url,
    })


@buyer_required
@require_GET
def news_list(request):
    page = Paginator(StorefrontNews.objects.filter(status="published", published_at__lte=timezone.now()), 12).get_page(request.GET.get("page", 1))
    return render(request, "resource_storefront/news_list.html", {"page_obj": page, "cart_count": sum(parse_cart(request.session, mode_for(request)).values())})


@buyer_required
@require_GET
def news_detail(request, slug):
    item = get_object_or_404(StorefrontNews, slug=slug, status="published", published_at__lte=timezone.now())
    linked = [{"cd": row.cd, "kind": "cd"} for row in item.newscdproduct_set.select_related("cd")]
    linked += [{"tech": row.tech, "kind": "tech"} for row in item.newstechproduct_set.select_related("tech")]
    rows = [product_by_id(row["kind"], (row.get("cd") or row.get("tech")).pk) for row in linked]
    return render(request, "resource_storefront/news_detail.html", {
        "item": item, "rows": [row for row in rows if row], "cart_count": sum(parse_cart(request.session, mode_for(request)).values()),
    })


def _cart_context(request, changes=False):
    cart = parse_cart(request.session, mode_for(request))
    rows, total = [], Decimal("0.00")
    snapshot = {}
    changed = bool(changes)
    for key, quantity in cart.items():
        kind, raw_id = key.split(":")
        row = product_by_id(kind, int(raw_id), mode_for(request))
        if not row:
            rows.append({"key": key, "quantity": quantity, "unavailable": True, "product": None})
            if key in request.session.get(session_key(request, "resource_cart_seen"), {}):
                changed = True
            continue
        row["key"] = key
        row["quantity"] = quantity
        row["line_total"] = row["price"] * quantity
        row["too_many"] = quantity > row["available"]
        total += row["line_total"]
        snapshot[key] = {"quantity": quantity, "price": str(row["price"]), "available": row["available"]}
        previous = request.session.get(session_key(request, "resource_cart_seen"), {}).get(key)
        if previous and previous != snapshot[key]:
            changed = True
            row["changed"] = True
        rows.append(row)
    config = config_for(request)
    version_data = {"rows":snapshot,"warehouse":config.warehouse_id if config else None,"mode":mode_for(request)}
    version = hashlib.sha256(json.dumps(version_data, sort_keys=True).encode()).hexdigest()
    checkout_allowed = bool(rows) and not changed and not any(row.get("unavailable") or row.get("too_many") for row in rows)
    if config and config.minimum_order_amount is not None and total < config.minimum_order_amount:
        checkout_allowed = False
    return {"rows": rows, "total": total, "version": version, "changes": changed, "snapshot": snapshot,
            "contact": request.wholesale_contact, "minimum": config.minimum_order_amount if config else None,
            "cart_count": sum(cart.values()), "checkout_allowed": checkout_allowed,
            "checkout_form": (RetailCheckoutForm if mode_for(request) == "retail" else CheckoutForm)(initial=request.session.get(session_key(request, "resource_checkout_draft"), {}))}


@buyer_required
@require_GET
def cart_view(request):
    context = _cart_context(request)
    if context["rows"] and not request.session.get(session_key(request, "resource_checkout_key")):
        request.session[session_key(request, "resource_checkout_key")] = uuid4().hex
    return render(request, "resource_storefront/cart.html", context)


def _remember_quantity(request, key):
    """Изменение количества не означает согласия с новой ценой и остатком."""
    current = _cart_context(request)["snapshot"]
    seen = request.session.get(session_key(request, "resource_cart_seen"), {}).copy()
    if key in current:
        seen[key] = {**seen.get(key, current[key]), "quantity": current[key]["quantity"]}
    else:
        seen.pop(key, None)
    request.session[session_key(request, "resource_cart_seen")] = seen


def _cart_reply(request, error=""):
    if _ajax(request):
        context = _cart_context(request)
        from django.template.loader import render_to_string
        return JsonResponse({"error": error, "cart_count": context["cart_count"],
                             "html": render_to_string("resource_storefront/_cart_content.html", context, request=request)}, status=400 if error else 200)
    if error:
        messages.error(request, error)
    return redirect(storefront_url(request, "cart"))


@buyer_required
@require_POST
def cart_add(request):
    operation = request.POST.get("operation", "")[:64]
    if operation and operation in request.session.get(session_key(request, "resource_cart_operations"), []):
        return JsonResponse({"cart_count": sum(parse_cart(request.session, mode_for(request)).values()), "message": "Товар уже добавлен."})
    kind = request.POST.get("kind", "")
    try:
        pk, quantity = int(request.POST.get("product_id", "")), int(request.POST.get("quantity", "1"))
    except ValueError:
        if _ajax(request):
            return JsonResponse({"error": "Укажите целое количество."}, status=400)
        return HttpResponse("Invalid product or quantity", status=400)
    row = product_by_id(kind, pk, mode_for(request))
    if not row or quantity < 1 or quantity > row["available"]:
        if _ajax(request):
            return JsonResponse({"error": "Товар или количество уже недоступны. Обновите каталог."}, status=409)
        messages.error(request, "Товар или количество уже недоступны.")
        return redirect(storefront_url(request, "catalogue"))
    cart = parse_cart(request.session, mode_for(request))
    was_empty = not cart
    key = row_key(kind, pk)
    cart[key] = min(row["available"], cart.get(key, 0) + quantity)
    set_cart(request.session, cart, mode_for(request))
    if was_empty:
        request.session[session_key(request, "resource_checkout_key")] = uuid4().hex
    _remember_quantity(request, key)
    if operation:
        request.session[session_key(request, "resource_cart_operations")] = (request.session.get(session_key(request, "resource_cart_operations"), []) + [operation])[-100:]
    if _ajax(request):
        return JsonResponse({"cart_count": sum(cart.values()), "message": "Добавлено в корзину", "quantity": cart[key]})
    messages.success(request, "Товар добавлен в корзину.")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = storefront_url(request, "catalogue")
    return redirect(next_url)


@buyer_required
@require_POST
def cart_update(request, key):
    cart = parse_cart(request.session, mode_for(request))
    try:
        quantity = int(request.POST.get("quantity", ""))
        kind, raw_id = key.split(":", 1)
        row = product_by_id(kind, int(raw_id), mode_for(request))
        if key not in cart or quantity < 1 or not row or quantity > row["available"]:
            raise ValueError
    except ValueError:
        return _cart_reply(request, "Укажите количество в пределах текущего остатка.")
    else:
        cart[key] = quantity
        set_cart(request.session, cart, mode_for(request))
        _remember_quantity(request, key)
    return _cart_reply(request)


@buyer_required
@require_POST
def cart_remove(request, key):
    cart = parse_cart(request.session, mode_for(request))
    cart.pop(key, None)
    set_cart(request.session, cart, mode_for(request))
    _remember_quantity(request, key)
    return _cart_reply(request)


@buyer_required
@require_POST
def cart_refresh(request):
    """Покупатель явно принимает текущие цены и наличие; позиции с нулём убираются."""
    cart = parse_cart(request.session, mode_for(request))
    updated = {}
    for key, quantity in cart.items():
        kind, raw_id = key.split(":")
        row = product_by_id(kind, int(raw_id), mode_for(request))
        if row:
            updated[key] = min(quantity, row["available"])
    set_cart(request.session, {key: qty for key, qty in updated.items() if qty > 0}, mode_for(request))
    request.session[session_key(request, "resource_cart_seen")] = _cart_context(request)["snapshot"]
    messages.info(request, "Корзина обновлена по текущим ценам и остаткам. Проверьте состав и подтвердите заказ ещё раз.")
    return redirect(storefront_url(request, "cart"))


@buyer_required
@require_POST
def checkout(request):
    if mode_for(request) == "retail":
        from .retail_views import retail_checkout
        return retail_checkout(request)
    checkout_form = CheckoutForm(request.POST)
    request.session[session_key(request, "resource_checkout_draft")] = {"extra_phone": request.POST.get("extra_phone", "")[:40], "comment": request.POST.get("comment", "")[:5000]}
    if not checkout_form.is_valid():
        context = _cart_context(request)
        context["checkout_form"] = checkout_form
        if _ajax(request):
            return JsonResponse({"error": "Проверьте поля оформления.", "fields": checkout_form.errors}, status=400)
        return render(request, "resource_storefront/cart.html", context, status=400)
    contact = request.wholesale_contact
    key = request.session.get(session_key(request, "resource_checkout_key")) or uuid4().hex
    request.session[session_key(request, "resource_checkout_key")] = key
    previous = StorefrontSubmission.objects.filter(contact=contact, idempotency_key=key).select_related("sale").first()
    if previous and previous.sale_id:
        if request.POST.get("cart_version") == previous.cart_digest:
            request.session.pop(session_key(request, "resource_cart"), None)
            request.session.pop(session_key(request, "resource_cart_seen"), None)
            request.session.pop(session_key(request, "resource_checkout_draft"), None)
            if _ajax(request):
                return JsonResponse({"url": storefront_url(request, "success", kwargs={"sale_id": previous.sale_id})})
            return redirect("resource_storefront:success", sale_id=previous.sale_id)
        return HttpResponse("Checkout key was already used for a different cart", status=409)
    context = _cart_context(request)
    if context["changes"] or not context["rows"] or any(row.get("unavailable") or row.get("too_many") for row in context["rows"]):
        if _ajax(request):
            return JsonResponse({"error": "Состав изменился. Откройте корзину и подтвердите новые цены и наличие.", "refresh": True}, status=409)
        messages.error(request, "Состав корзины изменился. Обновите корзину перед оформлением.")
        return redirect(storefront_url(request, "cart"))
    if request.POST.get("cart_version") != context["version"]:
        if _ajax(request):
            return JsonResponse({"error": "Цена или наличие изменились. Обновите корзину.", "refresh": True}, status=409)
        messages.warning(request, "Цена или наличие изменились после открытия корзины. Проверьте обновлённый состав.")
        return redirect(storefront_url(request, "cart"))
    config = config_for(request)
    if not config or not config.warehouse_id:
        return HttpResponse("Storefront warehouse is not configured", status=503)
    if config.minimum_order_amount is not None and context["total"] < config.minimum_order_amount:
        if _ajax(request):
            return JsonResponse({"error": "Сумма ниже минимальной суммы заказа."}, status=400)
        messages.error(request, "Сумма заказа ниже установленного минимума.")
        return redirect(storefront_url(request, "cart"))
    cart_digest = context["version"]
    existing = StorefrontSubmission.objects.filter(contact=contact, idempotency_key=key).select_related("sale").first()
    if existing and existing.sale_id:
        if _ajax(request):
            return JsonResponse({"url": storefront_url(request, "success", kwargs={"sale_id": existing.sale_id})})
        return redirect("resource_storefront:success", sale_id=existing.sale_id)
    lines = [{"product_type": row["kind"], "product_id": row["product"].pk, "quantity": row["quantity"]} for row in context["rows"]]
    try:
        with transaction.atomic():
            if not WholesaleAccessLink.objects.select_for_update().filter(
                pk=getattr(request, "wholesale_access_link_id", None), contact=contact, is_active=True,
            ).exists():
                raise ValidationError("Ссылка доступа отключена. Заказ не оформлен.")
            submission, created = StorefrontSubmission.objects.get_or_create(
                contact=contact, idempotency_key=key, defaults={"cart_digest": cart_digest},
            )
            if submission.cart_digest != cart_digest:
                return HttpResponse("Checkout key was already used for a different cart", status=409)
            if submission.sale_id:
                if _ajax(request):
                    return JsonResponse({"url": storefront_url(request, "success", kwargs={"sale_id": submission.sale_id})})
                return redirect("resource_storefront:success", sale_id=submission.sale_id)
            if not created:
                # A previous request rolled back before sale creation only if this record is still unbound.
                pass
            sale = create_sale(
                actor=None, warehouse_id=config.warehouse_id, price_type=Sale.PriceType.WHOLESALE,
                sale_type=Sale.SaleType.WHOLESALE, payment_method=Sale.PaymentMethod.CASH_POSTPAY,
                lines=lines,
            )
            sale.storefront_source = "resource_storefront"
            sale.wholesale_contact = contact
            sale.buyer_name_snapshot = contact.name
            sale.buyer_phone_snapshot = contact.phone
            sale.buyer_address_snapshot = contact.address
            sale.buyer_extra_phone = checkout_form.cleaned_data["extra_phone"]
            sale.buyer_comment = checkout_form.cleaned_data["comment"]
            sale.save(update_fields=("storefront_source", "wholesale_contact", "buyer_name_snapshot", "buyer_phone_snapshot", "buyer_address_snapshot", "buyer_extra_phone", "buyer_comment", "updated_at"))
            submission.sale = sale
            submission.save(update_fields=("sale",))
    except (ValidationError, IntegrityError) as exc:
        if _ajax(request):
            return JsonResponse({"error": "Заказ не оформлен: остаток изменился. Обновите корзину.", "refresh": True}, status=409)
        messages.error(request, str(exc) or "Заказ не оформлен: остаток уже изменился.")
        return redirect(storefront_url(request, "cart"))
    request.session.pop(session_key(request, "resource_cart"), None)
    request.session.pop(session_key(request, "resource_cart_seen"), None)
    request.session.pop(session_key(request, "resource_checkout_draft"), None)
    if _ajax(request):
        return JsonResponse({"url": storefront_url(request, "success", kwargs={"sale_id": sale.pk})})
    return redirect("resource_storefront:success", sale_id=sale.pk)


@buyer_required
@require_GET
def checkout_status(request):
    if mode_for(request) == "retail":
        from .retail_views import retail_checkout_status
        return retail_checkout_status(request)
    submission = StorefrontSubmission.objects.filter(contact=request.wholesale_contact,
        idempotency_key=request.session.get(session_key(request, "resource_checkout_key"), ""), sale__isnull=False).first()
    if submission:
        request.session.pop(session_key(request, "resource_cart"), None)
        request.session.pop(session_key(request, "resource_cart_seen"), None)
        request.session.pop(session_key(request, "resource_checkout_draft"), None)
    return JsonResponse({"url": storefront_url(request, "success", kwargs={"sale_id": submission.sale_id}) if submission else None})


@buyer_required
@require_GET
def order_success(request, sale_id):
    if mode_for(request) == "retail":
        from .retail_views import retail_success
        return retail_success(request, sale_id)
    sale = Sale.objects.filter(pk=sale_id, wholesale_contact=request.wholesale_contact, storefront_source="resource_storefront").first()
    if not sale:
        raise Http404
    return render(request, "resource_storefront/success.html", {"sale": sale, "cart_count": 0})


def _file_response(image):
    content_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    with image.open("rb") as source:
        response = HttpResponse(source.read(), content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@buyer_required
@require_GET
def product_photo(request, kind, pk, image_id):
    row = product_by_id(kind, pk, mode_for(request))
    if not row:
        raise Http404
    if image_id == 0:
        image = row["product"].title_image
    else:
        gallery = ProductImage.objects.filter(pk=image_id, product_kind=kind)
        gallery = gallery.filter(cd_id=pk) if kind == "cd" else gallery.filter(tech_id=pk)
        item = gallery.first()
        image = item.image if item else None
    if not image:
        raise Http404
    width = request.GET.get("w")
    if width in {"320", "640", "960"}:
        from PIL import Image, ImageOps, UnidentifiedImageError
        try:
            with image.open("rb") as source, Image.open(source) as original:
                thumbnail = ImageOps.exif_transpose(original)
                catalog_crop = image_id == 0 and request.GET.get("crop") == "card"
                if catalog_crop:
                    from .image_crops import crop_catalog_image
                    thumbnail = crop_catalog_image(thumbnail, row["product"], kind)
                thumbnail.thumbnail((int(width), round(int(width) * 4 / 3) if catalog_crop else int(width)))
                output = BytesIO()
                thumbnail.convert("RGB").save(output, "WEBP", quality=84)
            response = HttpResponse(output.getvalue(), content_type="image/webp")
            response["X-Content-Type-Options"] = "nosniff"
            return _private(response)
        except (FileNotFoundError, UnidentifiedImageError, OSError):
            raise Http404
    return _private(_file_response(image))


@buyer_required
@require_GET
def content_asset(request, kind, pk):
    if kind == "hero":
        config = config_for(request)
        image = getattr(config, "hero_image_mobile" if request.GET.get("mobile") == "1" else "hero_image_desktop", None) if config else None
    elif kind == "news":
        image = getattr(get_object_or_404(StorefrontNews, pk=pk, status="published", published_at__lte=timezone.now()), "cover")
    else:
        raise Http404
    if not image:
        raise Http404
    return _private(_file_response(image))


# Employee management
@permission_required_any("resource_storefront.manage_wholesale_contacts")
@require_GET
def contacts(request):
    term = request.GET.get("q", "").strip()[:120]
    rows = WholesaleContact.objects.filter(is_archived=False).prefetch_related("access_links")
    if term:
        rows = rows.filter(Q(name__icontains=term) | Q(phone__icontains=term) | Q(address__icontains=term))
    for row in rows:
        row.active_link = row.access_links.filter(is_active=True).first()
        row.copy_token = recover_token(row.active_link) if row.active_link else ""
    return render(request, "resource_storefront/contacts.html", {"contacts": rows, "query": term})


@permission_required_any("resource_storefront.manage_wholesale_contacts")
@require_POST
def contact_save(request, pk=None):
    contact = get_object_or_404(WholesaleContact, pk=pk) if pk else WholesaleContact()
    is_new = contact.pk is None
    contact.name = request.POST.get("name", "").strip()
    contact.phone = request.POST.get("phone", "").strip()
    contact.address = request.POST.get("address", "").strip()
    try:
        if not contact.name or not contact.phone:
            raise ValidationError("Имя и основной телефон обязательны.")
        if len(contact.phone) > 40 or not re.fullmatch(r"[+0-9() .\-/]{5,40}", contact.phone):
            raise ValidationError("Проверьте формат телефона.")
        contact.full_clean()
        with transaction.atomic():
            contact.save()
            if is_new:
                issue_link(contact, request.user)
        messages.success(request, "Контакт и персональная ссылка созданы." if is_new else "Контакт сохранён.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("resource_storefront:contacts")


@permission_required_any("resource_storefront.manage_wholesale_contacts")
@require_POST
def link_issue(request, pk):
    contact = get_object_or_404(WholesaleContact, pk=pk, is_archived=False)
    return_page = "resource_storefront:contacts"
    if request.POST.get("return_to") == "price_site_links" and (
        request.user.is_superuser or request.user.has_perm("price.view_price_page")
    ):
        return_page = "price:site_links"
    try:
        _, token = issue_link(contact, request.user)
    except ImproperlyConfigured:
        messages.error(request, "Не удалось создать ссылку: ключ шифрования не настроен. Обратитесь к администратору CRM.")
        return redirect(return_page)
    request.session["resource_issued_link"] = {"contact": contact.pk, "url": request.build_absolute_uri(reverse("resource_storefront:access", kwargs={"token": token}))}
    return redirect(return_page)


@permission_required_any("resource_storefront.manage_wholesale_contacts")
@require_POST
def link_revoke(request, pk):
    link = get_object_or_404(WholesaleAccessLink, pk=pk, is_active=True)
    link.is_active = False
    link.revoked_at = timezone.now()
    link.save(update_fields=("is_active", "revoked_at"))
    messages.success(request, "Доступ отключён. Открытые сессии также отозваны.")
    return redirect("resource_storefront:contacts")


@permission_required_any("resource_storefront.manage_storefront")
@require_GET
def manage(request):
    config = StorefrontSettings.get_solo()
    product_results = []
    product_q = request.GET.get("product_q", "").strip()[:120]
    if product_q:
        for kind, model, stock_model, fk in (("cd", CD, CDWarehouseStock, "cd_id"), ("tech", Tech, TechWarehouseStock, "tech_id")):
            products = model.objects.active().filter(name__icontains=product_q).order_by("name")[:30]
            availability = {}
            if config.warehouse_id:
                availability = {getattr(row, fk): row.quantity for row in stock_model.objects.filter(warehouse_id=config.warehouse_id, **{f"{fk[:-3]}__in": [p.pk for p in products]})}
            product_results.extend({"kind": kind, "product": p, "available": availability.get(p.pk, 0)} for p in products)
    return render(request, "resource_storefront/manage.html", {
        "config": config, "warehouses": Warehouse.objects.order_by("name"),
        "new_products": StorefrontProduct.objects.filter(placement="new"),
        "home_products": StorefrontProduct.objects.filter(placement="home"),
        "collections": ProductCollection.objects.prefetch_related("items"),
        "news": StorefrontNews.objects.all(),
        "product_results": product_results,
        "placement_choices": StorefrontProduct.Placement.choices,
    })


@permission_required_any("resource_storefront.manage_storefront")
@require_GET
def preview_start(request):
    request.session["resource_staff_preview"] = True
    return redirect(reverse("resource_storefront:home") + "?preview=drafts")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def settings_save(request):
    config = StorefrontSettings.get_solo()
    warehouse_id = request.POST.get("warehouse")
    if warehouse_id and not Warehouse.objects.filter(pk=warehouse_id).exists():
        messages.error(request, "Выберите существующий склад.")
        return redirect("resource_storefront:manage")
    config.warehouse_id = warehouse_id or None
    minimum = request.POST.get("minimum_order_amount", "").strip()
    try:
        config.minimum_order_amount = Decimal(minimum) if minimum else None
        if config.minimum_order_amount is not None and config.minimum_order_amount < 0:
            raise ValueError
    except Exception:
        messages.error(request, "Минимальная сумма должна быть положительным числом или быть пустой.")
        return redirect("resource_storefront:manage")
    for field in ("hero_title", "hero_description", "hero_button_label", "hero_button_url", "about_text", "wholesale_terms", "public_contacts"):
        setattr(config, field, request.POST.get(field, "").strip())
    if config.hero_button_url and not (config.hero_button_url.startswith("/") or config.hero_button_url.startswith("https://")):
        messages.error(request, "Адрес кнопки должен быть внутренним путём или HTTPS-ссылкой.")
        return redirect("resource_storefront:manage")
    from catalog.product_media import validate_product_image
    for field in ("hero_image_desktop", "hero_image_mobile"):
        if request.FILES.get(field):
            try:
                upload = validate_product_image(request.FILES[field])
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
                return redirect("resource_storefront:manage")
            setattr(config, field, upload)
    config.save()
    messages.success(request, "Настройки витрины сохранены.")
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def slot_add(request):
    kind = request.POST.get("kind")
    try:
        product_id = int(request.POST.get("product_id", ""))
        placement = request.POST.get("placement")
        model = CD if kind == "cd" else Tech if kind == "tech" else None
        product = model.objects.active().get(pk=product_id) if model else None
        if not product or placement not in StorefrontProduct.Placement.values:
            raise ValueError
        relation = {kind: product}
        if not product.wholesale_price or product.wholesale_price <= 0:
            raise ValueError
        StorefrontProduct.objects.get_or_create(placement=placement, **relation, defaults={"sort_order": StorefrontProduct.objects.filter(placement=placement).count()})
        messages.success(request, "Товар добавлен в подборку. Остаток проверяется при каждом показе.")
    except (ValueError, CD.DoesNotExist, Tech.DoesNotExist):
        messages.error(request, "Выберите доступный товар с положительной оптовой ценой.")
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def product_publication(request, kind, pk):
    model = CD if kind == "cd" else Tech if kind == "tech" else None
    if model is None:
        raise Http404
    product = get_object_or_404(model.objects.active(), pk=pk)
    enabled = request.POST.get("enabled") == "1"
    if product.wholesale_site_enabled != enabled:
        old_value = product.wholesale_site_enabled
        with transaction.atomic():
            product.wholesale_site_enabled = enabled
            product.save(update_fields=("wholesale_site_enabled",))
            record_product_changes(
                actor=request.user,
                instance=product,
                changes=[field_change(
                    field_name="wholesale_site_enabled",
                    field_label=str(product._meta.get_field("wholesale_site_enabled").verbose_name),
                    old_value=old_value,
                    new_value=enabled,
                )],
                source=ProductChangeEvent.Source.CRM,
                action_kind="storefront_publication",
                action_object_id=product.pk,
                action_label="Публикация товара на оптовой витрине",
            )
    messages.success(request, "Товар опубликован на витрине." if enabled else "Товар скрыт с оптовой витрины.")
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def slot_remove(request, pk):
    get_object_or_404(StorefrontProduct, pk=pk).delete()
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def news_save(request, pk=None):
    item = get_object_or_404(StorefrontNews, pk=pk) if pk else StorefrontNews()
    item.title = request.POST.get("title", "").strip()[:220]
    item.slug = request.POST.get("slug", "").strip() or slugify(item.title, allow_unicode=True)
    item.excerpt = request.POST.get("excerpt", "").strip()
    item.body = request.POST.get("body", "").strip()
    published = request.POST.get("status") == "published"
    item.status = StorefrontNews.Status.PUBLISHED if published else StorefrontNews.Status.DRAFT
    item.published_at = item.published_at or timezone.now() if published else None
    if request.FILES.get("cover"):
        from catalog.product_media import validate_product_image
        try:
            item.cover = validate_product_image(request.FILES["cover"])
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("resource_storefront:manage")
    if not item.title or not item.slug:
        messages.error(request, "Заголовок новости обязателен.")
    else:
        try:
            item.full_clean()
            item.save()
            messages.success(request, "Новость сохранена.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def news_unpublish(request, pk):
    item = get_object_or_404(StorefrontNews, pk=pk)
    item.status = StorefrontNews.Status.DRAFT
    item.published_at = None
    item.save(update_fields=("status", "published_at", "updated_at"))
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def collection_save(request, pk=None):
    collection = get_object_or_404(ProductCollection, pk=pk) if pk else ProductCollection()
    collection.title = request.POST.get("title", "").strip()[:160]
    collection.slug = request.POST.get("slug", "").strip() or slugify(collection.title, allow_unicode=True)
    collection.is_visible = request.POST.get("is_visible") == "1"
    try:
        collection.sort_order = int(request.POST.get("sort_order", "0"))
        if not collection.title:
            raise ValueError
        collection.full_clean()
        collection.save()
        messages.success(request, "Подборка сохранена.")
    except (ValidationError, ValueError) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Укажите название и целый порядок отображения.")
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def collection_product_add(request, pk):
    collection = get_object_or_404(ProductCollection, pk=pk)
    kind = request.POST.get("kind")
    try:
        model = CD if kind == "cd" else Tech if kind == "tech" else None
        product = model.objects.active().get(pk=int(request.POST.get("product_id", ""))) if model else None
        if not product:
            raise ValueError
        relation = {kind: product}
        CollectionProduct.objects.get_or_create(collection=collection, **relation, defaults={"sort_order": collection.items.count()})
    except (ValueError, CD.DoesNotExist, Tech.DoesNotExist):
        messages.error(request, "Не удалось добавить выбранный товар.")
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def collection_product_remove(request, pk):
    get_object_or_404(CollectionProduct, pk=pk).delete()
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def news_product_add(request, pk):
    item = get_object_or_404(StorefrontNews, pk=pk)
    kind = request.POST.get("kind")
    try:
        model = CD if kind == "cd" else Tech if kind == "tech" else None
        product = model.objects.active().get(pk=int(request.POST.get("product_id", ""))) if model else None
        if not product:
            raise ValueError
        relation = {kind: product}
        through = NewsCDProduct if kind == "cd" else NewsTechProduct
        through.objects.get_or_create(news=item, **relation, defaults={"sort_order": through.objects.filter(news=item).count()})
    except (ValueError, CD.DoesNotExist, Tech.DoesNotExist):
        messages.error(request, "Не удалось добавить товар к новости.")
    return redirect("resource_storefront:manage")


@permission_required_any("resource_storefront.manage_storefront")
@require_POST
def news_product_remove(request, kind, pk):
    model = NewsCDProduct if kind == "cd" else NewsTechProduct if kind == "tech" else None
    if not model:
        raise Http404
    get_object_or_404(model, pk=pk).delete()
    return redirect("resource_storefront:manage")
