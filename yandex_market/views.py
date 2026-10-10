"""Интерфейс Маркета: каждое изменение проверяет право и подтверждение на сервере."""
import json
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters

from catalog.models import CD, Tech
from catalog.product_search import filter_products_by_text
from warehouse.inventory import global_stock
from warehouse.models import Warehouse
from .client import MarketError, YandexMarketClient, api_key
from .content import CONTENT_FIELDS, LOCKED_CARD, OFFER_SCHEMA, DELETE_FIELDS
from .documents import save_image
from .forms import ContentForm, IntegrationForm
from .models import ApiLog, Integration, LabelDocument, Media, OfferConnection, OrderMetadata, RemoteOffer, ReturnMetadata, SyncJob
from .orders import accept_return, available_actions, action_payload
from .packing import validate_boxes
from .queue import enqueue, product_after_commit
from .services import activate, audit, bind_offer, check_connection, create_offer, refresh_category, refresh_offer, unlink_offer, store_api_key, connections_with_stock, store_offer


def access(permission="view_integration", *, post=False):
    def decorate(view):
        @wraps(view)
        def guarded(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except (ValidationError, MarketError, IntegrityError) as exc:
                error = "Связь уже изменена другим пользователем. Обновите страницу." if isinstance(exc, IntegrityError) else " ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                if request.method == "POST":
                    messages.error(request, error)
                    return redirect("yandex_market:dashboard")
                return render(request, "yandex_market/error.html", {"error": error}, status=400)
        wrapped = require_POST(guarded) if post else guarded
        return login_required(permission_required(f"yandex_market.{permission}", raise_exception=True)(wrapped))
    return decorate


def confirmed(request):
    if request.POST.get("confirm") != "yes":
        raise ValidationError("Подтвердите действие перед отправкой.")


def connection_query():
    return OfferConnection.objects.select_related("integration", "remote_offer", "cd", "tech")


def selected_integration(request):
    key = request.GET.get("integration") or request.POST.get("integration")
    return get_object_or_404(Integration, pk=key) if key and key.isdecimal() else Integration.objects.order_by("pk").first()


@access()
def dashboard(request):
    integration = selected_integration(request)
    tab = request.GET.get("tab", "overview")
    if tab not in {"overview", "offers", "connections", "orders", "returns", "errors", "mismatches", "log"}:
        tab = "overview"
    rows, totals = [], {}
    query = request.GET.get("q", "").strip()
    if integration:
        totals = {"offers": integration.offers.count(), "connections": integration.connections.filter(active=True).count(),
                  "orders": integration.orders.count(), "errors": integration.jobs.filter(state="error").count()}
        if tab == "offers":
            rows = integration.offers.prefetch_related(Prefetch("connections", queryset=connection_query())).all()
            if query:
                needle = query.casefold()
                matching = [pk for pk, name, offer_id, sku in rows.values_list("pk", "name", "offer_id", "market_sku").iterator() if any(needle in str(value or "").casefold() for value in (name, offer_id, sku))]
                rows = rows.filter(pk__in=matching)
            if request.GET.get("unbound"):
                rows = rows.exclude(connections__active=True)
        elif tab in {"connections", "mismatches"}:
            rows = connections_with_stock(connection_query().filter(integration=integration, active=True)).order_by("pk")
            if query:
                cd_ids = filter_products_by_text(CD.objects.active(), query, product_kind="cd").values("pk")
                tech_ids = filter_products_by_text(Tech.objects.active(), query, product_kind="tech").values("pk")
                rows = rows.filter(Q(remote_offer__offer_id__icontains=query) | Q(cd_id__in=cd_ids) | Q(tech_id__in=tech_ids))
            if request.GET.get("kind") in {"cd", "tech"}:
                rows = rows.filter(**{request.GET["kind"] + "__isnull": False})
            if request.GET.get("enabled") in {"yes", "no"}:
                rows = rows.filter(sell_on_yandex=request.GET["enabled"] == "yes")
            if request.GET.get("card"):
                rows = rows.filter(remote_offer__card_status=request.GET["card"])
            if request.GET.get("error"):
                rows = rows.exclude(last_error="")
            if request.GET.get("unsynced"):
                rows = rows.exclude(state="synced")
            if tab == "mismatches":
                mismatches = []
                for row in rows:
                    row.desired_stock = row.physical_stock if row.sell_on_yandex and not row.product.is_archived else 0
                    if row.remote_offer.remote_stock != row.desired_stock or row.remote_offer.remote_price != row.product.yandex_market_price:
                        mismatches.append(row)
                rows = mismatches
        elif tab == "orders":
            rows = integration.orders.select_related("sale").all()
            if query:
                rows = rows.filter(order_id__icontains=query)
        elif tab == "returns":
            rows = ReturnMetadata.objects.filter(order__integration=integration).select_related("order", "warehouse").order_by("-pk")
        elif tab == "errors":
            rows = integration.jobs.exclude(last_error="").order_by("-updated_at")
        elif tab == "log":
            rows = ApiLog.objects.filter(integration=integration)
    return render(request, "yandex_market/dashboard.html", {"integration": integration, "integrations": Integration.objects.all(),
        "tab": tab, "page": Paginator(rows, 40).get_page(request.GET.get("page")), "q": query, "totals": totals,
        "public_url": settings.YANDEX_MARKET_PUBLIC_URL})


@access("manage_settings")
@sensitive_post_parameters("new_api_key")
def settings_view(request, pk=None):
    integration = get_object_or_404(Integration, pk=pk) if pk else None
    form = IntegrationForm(request.POST or None, instance=integration)
    if request.method == "POST" and form.is_valid():
        new_key = form.cleaned_data.get("new_api_key")
        if new_key:
            store_api_key(new_key)
        with transaction.atomic():
            instance = form.save(commit=False)
            if new_key or any(field in form.changed_data for field in ("business_id", "campaign_id", "partner_warehouse_id", "stock_api", "price_scope")):
                instance.checked_at = None
                instance.enabled = False
            instance.save()
            audit(instance, request.user, "settings", instance.pk, fields=form.changed_data)
        messages.success(request, "Настройки сохранены.")
        return redirect("yandex_market:settings", pk=instance.pk)
    return render(request, "yandex_market/settings.html", {"form": form, "integration": integration, "key_configured": bool(api_key()), "public_url": settings.YANDEX_MARKET_PUBLIC_URL})


@access("edit_content")
def categories(request, pk):
    connection = get_object_or_404(connection_query(), pk=pk, active=True)
    integration = connection.integration
    if request.method == "POST":
        tree = YandexMarketClient(integration, actor=request.user).call("getCategoriesTree", body={}).get("result", {})
        integration.configuration["category_tree"] = tree
        integration.save(update_fields=["configuration"])
        return redirect("yandex_market:categories", pk=pk)
    tree = integration.configuration.get("category_tree", {})
    query = request.GET.get("q", "").strip().casefold()
    rows = []
    def flatten(node, parent=""):
        name = (parent + " / " if parent else "") + node.get("name", "")
        children = node.get("children") or []
        if not children and node.get("id") and (not query or query in name.casefold() or query == str(node["id"])):
            rows.append({"id": node["id"], "name": name})
        for child in children:
            flatten(child, name)
    flatten(tree)
    return render(request, "yandex_market/categories.html", {"connection": connection, "q": request.GET.get("q", ""), "page": Paginator(rows, 50).get_page(request.GET.get("page"))})


@access("manage_settings", post=True)
def check(request, pk):
    integration = get_object_or_404(Integration, pk=pk)
    check_connection(integration, client=YandexMarketClient(integration, actor=request.user))
    audit(integration, request.user, "connection_checked", pk)
    messages.success(request, "Ключ, FBS-магазин, валюта и склад проверены.")
    return redirect("yandex_market:settings", pk=pk)


@access("retry_sync", post=True)
def synchronize(request, pk):
    integration = get_object_or_404(Integration, pk=pk)
    kind = "catalog" if request.POST.get("scope") == "catalog" else "reconcile"
    if kind == "reconcile":
        confirmed(request)
        if not integration.enabled:
            raise ValidationError("Сначала включите фоновый обмен.")
    enqueue(integration, kind, "manual", actor=request.user)
    messages.success(request, "Задание добавлено в очередь.")
    return redirect(reverse("yandex_market:dashboard") + f"?integration={pk}&tab=errors")


@access("bind_offer")
def bind(request, pk):
    remote = get_object_or_404(RemoteOffer.objects.select_related("integration"), pk=pk)
    current = connection_query().filter(remote_offer=remote, active=True).first()
    if current and not request.user.has_perm("yandex_market.rebind_offer"):
        raise PermissionDenied
    query = request.GET.get("q", "").strip()
    kind, product_id = request.GET.get("kind"), request.GET.get("product")
    product, token, products = None, None, []
    if kind in {"cd", "tech"} and product_id and product_id.isdecimal():
        product = get_object_or_404({"cd": CD, "tech": Tech}[kind].objects.active(), pk=product_id)
        token = signing.dumps({"remote": remote.pk, "kind": kind, "product": product.pk, "user": request.user.pk, "current": current.pk if current else None}, salt="ym-bind")
    elif query:
        for product_kind, model in (("cd", CD), ("tech", Tech)):
            products.extend((product_kind, item) for item in filter_products_by_text(model.objects.active(), query, product_kind=product_kind)[:30])
    if request.method == "POST":
        confirmed(request)
        try:
            data = signing.loads(request.POST.get("token", ""), salt="ym-bind", max_age=1800)
        except signing.BadSignature:
            raise ValidationError("Подтверждение устарело. Выберите товар заново.") from None
        if data["user"] != request.user.pk or data["remote"] != remote.pk or data["current"] != (current.pk if current else None):
            raise ValidationError("Привязка изменилась. Проверьте её заново.")
        remote = refresh_offer(remote, client=YandexMarketClient(remote.integration, actor=request.user))
        if remote.category_id:
            refresh_category(remote.category_id, client=YandexMarketClient(remote.integration, actor=request.user))
        replacement = {"product_kind": data["kind"], "product_id": data["product"]}
        connection = unlink_offer(current.pk, request.user, replacement=replacement) if current else bind_offer(remote_id=remote.pk, actor=request.user, **replacement)
        messages.success(request, "Связь сохранена. Проверьте сравнение и отдельно включите управление.")
        return redirect("yandex_market:connection", pk=connection.pk)
    return render(request, "yandex_market/bind.html", {"remote": remote, "current": current, "product": product, "kind": kind, "token": token,
        "products": products, "q": query, "stock": global_stock(product) if product else None})


@access("bind_offer", post=True)
def new_offer(request):
    confirmed(request)
    integration = get_object_or_404(Integration, pk=request.POST.get("integration"))
    kind = request.POST.get("kind")
    if kind not in {"cd", "tech"}:
        raise ValidationError("Неизвестный тип товара.")
    product = get_object_or_404({"cd": CD, "tech": Tech}[kind].objects.active(), pk=request.POST.get("product"))
    offer_id = f"GB-{kind.upper()}-{product.pk}"
    existing = YandexMarketClient(integration, actor=request.user).call("getOfferMappings", body={"offerIds": [offer_id]}).get("result", {}).get("offerMappings", [])
    for row in existing:
        if row.get("offer", {}).get("offerId") == offer_id:
            remote = store_offer(integration, row)
            messages.info(request, "Этот offerId уже существует на Маркете. Сначала подтвердите привязку существующей карточки.")
            return redirect("yandex_market:bind", pk=remote.pk)
    connection = create_offer(integration=integration, product_kind=kind, product_id=product.pk, actor=request.user)
    return redirect("yandex_market:connection", pk=connection.pk)


@access()
def connection_detail(request, pk):
    connection = get_object_or_404(connection_query(), pk=pk)
    form = ContentForm(request.POST or None, connection=connection)
    if request.method == "POST":
        if not request.user.has_perm("yandex_market.edit_content"):
            raise PermissionDenied
        if not connection.active:
            raise ValidationError("Историческую связь нельзя редактировать.")
        if form.is_valid():
            with transaction.atomic():
                if not OfferConnection.objects.filter(pk=pk, revision=form.cleaned_data["revision"]).update(revision=F("revision") + 1):
                    raise ValidationError("Товар изменён другим пользователем. Обновите форму.")
                dirty = set(connection.dirty_fields)
                content = dict(connection.content)
                for key, value in form.cleaned_data["content"].items():
                    if value != form.baseline.get(key):
                        content[key] = value
                        dirty.add(key)
                parameters = form.cleaned_data["parameters"]
                if form.parameter_schema and parameters != form.initial_parameters:
                    if not parameters and form.initial_parameters:
                        raise ValidationError("Удаление характеристик выполняется отдельным действием очистки.")
                    dirty.add("parameterValues")
                OfferConnection.objects.filter(pk=pk).update(content=content, parameters=parameters if form.parameter_schema else connection.parameters, dirty_fields=sorted(dirty))
                if form.cleaned_data["content"].get("weightDimensions"):
                    from .product_dimensions import save_dimensions
                    save_dimensions(connection.product, form.cleaned_data["content"]["weightDimensions"], actor=request.user,
                                    only_missing=False, source="Редактор карточки Яндекс Маркета")
                audit(connection.integration, request.user, "content_saved", pk, fields=sorted(dirty))
                product_after_commit(pk)
            messages.success(request, "Изменения сохранены; у управляемого товара поставлены в очередь.")
            return redirect("yandex_market:connection", pk=pk)
    return render(request, "yandex_market/connection.html", {"connection": connection, "form": form, "stock": global_stock(connection.product),
        "media": connection.media.filter(active=True), "locked": connection.remote_offer.card_status == LOCKED_CARD,
        "delete_options": DELETE_FIELDS, "public_url": settings.YANDEX_MARKET_PUBLIC_URL,
        "history": connection.integration.auditevent_set.filter(entity_id=str(pk)).select_related("actor").order_by("-pk")[:50]})


@access("edit_content", post=True)
def content_action(request, pk):
    connection = get_object_or_404(connection_query(), pk=pk, active=True)
    action = request.POST.get("action")
    if action == "refresh":
        if not connection.is_new:
            refresh_offer(connection.remote_offer, client=YandexMarketClient(connection.integration, actor=request.user))
        if connection.category_id:
            refresh_category(connection.category_id, client=YandexMarketClient(connection.integration, actor=request.user))
        return redirect("yandex_market:connection", pk=pk)
    confirmed(request)
    if action == "activate":
        if not request.user.has_perm("yandex_market.retry_sync"):
            raise PermissionDenied
        activate(pk, request.user, sell=request.POST.get("sell") == "yes")
        return redirect("yandex_market:connection", pk=pk)
    if connection.remote_offer.card_status == LOCKED_CARD:
        raise ValidationError("Контент этой карточки доступен только для просмотра.")
    schema = None
    if action == "category":
        category_id = request.POST.get("category", "")
        if not category_id.isdecimal() or int(category_id) <= 0:
            raise ValidationError("Укажите ID категории Маркета.")
        schema = refresh_category(int(category_id), client=YandexMarketClient(connection.integration, actor=request.user))
    with transaction.atomic():
        OfferConnection.objects.filter(pk=pk).update(revision=F("revision") + 1)
        connection = connection_query().get(pk=pk)
        dirty = set(connection.dirty_fields)
        if action == "category":
            connection.category_id = schema.category_id
            connection.parameters = []
            dirty.update(["marketCategoryId", "parameterValues"])
        elif action == "clear":
            field = request.POST.get("field")
            allowed = DELETE_FIELDS
            if field not in allowed:
                raise ValidationError("API не поддерживает очистку этого поля.")
            connection.delete_fields = sorted(set(connection.delete_fields) | {field})
            connection.content.pop(DELETE_FIELDS[field], None)
            dirty.discard(DELETE_FIELDS[field])
            if field == "PARAMETERS":
                connection.parameters = []
            if field == "PICTURES":
                connection.media.filter(active=True).update(active=False)
        elif action == "upload":
            uploads = request.FILES.getlist("images")
            if not uploads or len(uploads) + connection.media.filter(active=True).count() > 30:
                raise ValidationError("Выберите изображения; максимум 30 файлов.")
            for upload in uploads:
                save_image(connection, upload)
            connection.content["pictures"] = []
            dirty.add("pictures")
        elif action == "media_order":
            ids = request.POST.getlist("media")
            if set(ids) != {str(i) for i in connection.media.filter(active=True).values_list("pk", flat=True)} or len(ids) != len(set(ids)):
                raise ValidationError("Состав фотографий изменился. Обновите страницу.")
            for index, media_id in enumerate(ids):
                connection.media.filter(pk=media_id).update(position=index)
            dirty.add("pictures")
        elif action == "media_remove":
            media = get_object_or_404(Media, pk=request.POST.get("media"), connection=connection)
            # Файл остаётся доступен по уже переданной постоянной ссылке до очистки хранилища.
            media.active = False
            media.save(update_fields=["active"])
            dirty.add("pictures")
        else:
            raise ValidationError("Неизвестное действие с контентом.")
        connection.dirty_fields = sorted(dirty)
        connection.save(update_fields=["category_id", "parameters", "content", "dirty_fields", "delete_fields"])
        audit(connection.integration, request.user, action, pk)
        product_after_commit(pk)
    return redirect("yandex_market:connection", pk=pk)


@access("rebind_offer", post=True)
def unlink(request, pk):
    confirmed(request)
    unlink_offer(pk, request.user)
    messages.success(request, "Связь отключена. Товар и история Маркета сохранены.")
    return redirect("yandex_market:dashboard")


@access()
def order_detail(request, pk):
    order = get_object_or_404(OrderMetadata.objects.select_related("sale", "integration"), pk=pk)
    return render(request, "yandex_market/order.html", {"order": order, "actions": available_actions(order), "returns": order.returns.all(),
        "labels": order.labels.order_by("-pk"), "warehouses": Warehouse.objects.all()})


@access("manage_orders", post=True)
def order_action(request, pk):
    confirmed(request)
    order = get_object_or_404(OrderMetadata.objects.select_related("integration"), pk=pk)
    action = request.POST.get("action")
    payload = {"order_id": order.order_id}
    if action == "refresh":
        kind = "order"
    elif action == "boxes":
        try:
            boxes = json.loads(request.POST.get("boxes", ""))
        except ValueError:
            raise ValidationError("Не удалось прочитать состав коробок.") from None
        validate_boxes(order, boxes)
        payload["boxes"] = boxes
        kind = "boxes"
    else:
        action_payload(order, action)
        payload["action"] = action
        kind = "order_action"
    enqueue(order.integration, kind, order.order_id, payload, actor=request.user)
    audit(order.integration, request.user, kind, order.order_id, requested_action=action)
    messages.success(request, "Задание поставлено в очередь. Статус обновится после ответа Маркета.")
    return redirect("yandex_market:order", pk=pk)


@access("accept_return", post=True)
def return_accept(request, pk):
    confirmed(request)
    returned = get_object_or_404(ReturnMetadata.objects.select_related("order"), pk=pk)
    warehouse = get_object_or_404(Warehouse, pk=request.POST.get("warehouse"))
    accept_return(return_pk=returned.pk, warehouse_id=warehouse.pk, actor=request.user)
    messages.success(request, "Физический возврат принят на выбранный склад.")
    return redirect("yandex_market:order", pk=returned.order_id)


@access("print_labels", post=True)
def label_request(request):
    confirmed(request)
    integration = get_object_or_404(Integration, pk=request.POST.get("integration"))
    format_name = request.POST.get("format", "A7")
    if format_name not in {"A7", "A4", "A9", "A9_HORIZONTALLY"}:
        raise ValidationError("Неизвестный формат ярлыка.")
    ids = request.POST.getlist("orders")
    orders = list(integration.orders.filter(pk__in=[int(i) for i in ids if i.isdecimal()]))
    if not orders or len(orders) != len(set(ids)) or len(orders) > 1000:
        raise ValidationError("Выберите от 1 до 1000 заказов одного магазина.")
    values = {"integration": integration, "format": format_name, "created_by": request.user}
    if len(orders) == 1:
        values["order"] = orders[0]
        box_id, shipment_id = request.POST.get("box"), request.POST.get("shipment")
        if box_id or shipment_id:
            if not box_id or not shipment_id or not box_id.isdecimal() or not shipment_id.isdecimal():
                raise ValidationError("Укажите идентификаторы коробки и отправления.")
            values.update(box_id=int(box_id), shipment_id=int(shipment_id))
    else:
        values["order_ids"] = [o.order_id for o in orders]
    with transaction.atomic():
        document = LabelDocument.objects.create(**values)
        transaction.on_commit(lambda: enqueue(integration, "label", document.pk, {"document_id": document.pk}, actor=request.user))
        audit(integration, request.user, "labels_requested", document.pk, orders=[o.order_id for o in orders])
    return redirect("yandex_market:label", pk=document.pk)


@access("print_labels")
def label_detail(request, pk):
    return render(request, "yandex_market/label.html", {"document": get_object_or_404(LabelDocument, pk=pk)})


@access("print_labels")
def label_file(request, pk):
    document = get_object_or_404(LabelDocument, pk=pk, state="done")
    if not document.file:
        raise Http404
    response = FileResponse(document.file.open("rb"), content_type="application/pdf", as_attachment=request.GET.get("download") == "1", filename=f"market-labels-{pk}.pdf")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def public_media(request, public_id):
    media = get_object_or_404(Media, public_id=public_id)
    response = FileResponse(media.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@access("retry_sync", post=True)
def retry(request, pk):
    confirmed(request)
    job = get_object_or_404(SyncJob.objects.select_related("integration"), pk=pk)
    if job.kind in {"order_action", "boxes"} and not request.user.has_perm("yandex_market.manage_orders"):
        raise PermissionDenied
    if job.kind == "label" and not request.user.has_perm("yandex_market.print_labels"):
        raise PermissionDenied
    if job.state == "running":
        raise ValidationError("Задание ещё выполняется.")
    SyncJob.objects.filter(pk=pk).exclude(state="running").update(state="pending", attempts=0, last_error="", run_after=timezone.now(), actor=request.user)
    audit(job.integration, request.user, "retry", pk)
    return redirect(reverse("yandex_market:dashboard") + f"?integration={job.integration_id}&tab=errors")
