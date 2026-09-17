import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from catalog.models import CD, Tech
from core.decorators import permission_required_any

from .client import AvitoAPIError
from .forms import AvitoPhotoForm, AvitoProfileForm, CredentialForm, ProductTargetForm
from .models import (
    AvitoListingConnection,
    AvitoProductPhoto,
    AvitoProductProfile,
    AvitoRemoteListing,
    AvitoSyncJob,
    AvitoSyncLog,
    IntegrationCredential,
)
from .queue import enqueue_periodic, enqueue_profile_sync_after_commit
from .services import (
    bind_listing,
    check_avito_connection,
    get_avito_credential,
    get_or_create_profile,
    global_stock,
    rebind_listing,
    save_avito_credentials,
    update_profile,
)

logger = logging.getLogger("gamebat.business")


def _error_text(exc):
    if isinstance(exc, ValidationError):
        return " ".join(exc.messages)
    return str(exc)


@permission_required_any("integrations.view_integrations")
def api_keys(request):
    credential = get_avito_credential()
    form = CredentialForm()
    return render(request, "integrations/api_keys.html", {"credential": credential, "form": form})


@require_POST
@permission_required_any("integrations.manage_integration_credentials")
def credentials_save(request):
    form = CredentialForm(request.POST)
    if form.is_valid():
        try:
            save_avito_credentials(actor=request.user, **form.cleaned_data)
        except (ValidationError, AvitoAPIError) as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Параметры Avito зашифрованы и подключение проверено.")
    else:
        messages.error(request, "Проверьте параметры подключения.")
    return redirect("integrations:api_keys")


@require_POST
@permission_required_any("integrations.manage_integration_credentials")
def credentials_check(request):
    try:
        check_avito_connection(actor=request.user)
    except (ValidationError, AvitoAPIError) as exc:
        messages.error(request, _error_text(exc))
    else:
        messages.success(request, "Подключение к Avito работает.")
    return redirect("integrations:api_keys")


@permission_required_any("integrations.view_avito_integration")
def avito_dashboard(request):
    credential = get_avito_credential()
    context = {
        "credential": credential,
        "linked_count": AvitoListingConnection.objects.count(),
        "unlinked_count": AvitoRemoteListing.objects.filter(connection__isnull=True).count(),
        "error_count": AvitoProductProfile.objects.filter(
            Q(cd__is_archived=False) | Q(tech__is_archived=False),
            sync_status=AvitoProductProfile.SyncStatus.ERROR,
        ).count(),
        "last_log": AvitoSyncLog.objects.filter(result=AvitoSyncLog.Result.SUCCESS).first(),
        "pending_count": AvitoSyncJob.objects.filter(status=AvitoSyncJob.Status.PENDING).count(),
    }
    return render(request, "integrations/avito_dashboard.html", context)


@require_POST
@permission_required_any("integrations.manual_avito_sync")
def manual_sync(request):
    enqueue_periodic(AvitoSyncJob.JobType.REFRESH)
    enqueue_periodic(AvitoSyncJob.JobType.RECONCILE, delay_seconds=2)
    messages.success(request, "Синхронизация поставлена в очередь.")
    return redirect("integrations:avito")


@permission_required_any("integrations.view_avito_integration")
def connections(request):
    query = str(request.GET.get("q") or "").strip()
    unlinked = AvitoRemoteListing.objects.filter(connection__isnull=True)
    linked = AvitoListingConnection.objects.select_related(
        "remote_listing", "profile", "profile__cd", "profile__tech"
    )
    if query:
        remote_filter = Q(title__icontains=query) | Q(status__icontains=query)
        linked_filter = (
            Q(remote_listing__title__icontains=query) | Q(remote_listing__status__icontains=query)
            | Q(profile__cd__name__icontains=query) | Q(profile__tech__name__icontains=query)
        )
        if query.isdigit():
            remote_filter |= Q(avito_item_id=int(query))
            linked_filter |= Q(remote_listing__avito_item_id=int(query)) | Q(profile__cd_id=int(query)) | Q(profile__tech_id=int(query))
        unlinked = unlinked.filter(remote_filter)
        linked = linked.filter(linked_filter)
    context = {
        "query": query,
        "unlinked_page": Paginator(unlinked, 25).get_page(request.GET.get("unlinked_page")),
        "linked_page": Paginator(linked, 25).get_page(request.GET.get("linked_page")),
    }
    return render(request, "integrations/connections.html", context)


@require_POST
@permission_required_any("integrations.manual_avito_sync")
def listings_refresh(request):
    enqueue_periodic(AvitoSyncJob.JobType.REFRESH)
    messages.success(request, "Обновление списка объявлений поставлено в очередь.")
    return redirect("integrations:connections")


@permission_required_any("integrations.bind_avito_listing")
def listing_bind(request, pk):
    listing = get_object_or_404(AvitoRemoteListing, pk=pk, connection__isnull=True)
    query = request.GET.get("q", "")
    form = ProductTargetForm(request.POST or None, query=query)
    if request.method == "POST" and form.is_valid():
        kind, product = form.cleaned_data["product_ref"]
        try:
            connection = bind_listing(listing=listing, product=product, product_kind=kind, actor=request.user)
        except (ValidationError, AvitoAPIError) as exc:
            form.add_error(None, _error_text(exc))
        else:
            flag_status = "включён" if connection.profile.sell_on_avito else "выключен: объявление неактивно"
            messages.success(request, f"Объявление связано с товаром. Флаг продажи на Avito {flag_status}.")
            return redirect("integrations:connections")
    return render(request, "integrations/bind.html", {"listing": listing, "form": form, "query": query})


@permission_required_any("integrations.rebind_avito_listing")
def listing_rebind(request, pk):
    connection = get_object_or_404(
        AvitoListingConnection.objects.select_related("remote_listing", "profile", "profile__cd", "profile__tech"), pk=pk
    )
    query = request.GET.get("q", "")
    form = ProductTargetForm(request.POST or None, query=query)
    if request.method == "POST" and form.is_valid():
        kind, product = form.cleaned_data["product_ref"]
        try:
            rebind_listing(connection=connection, product=product, product_kind=kind, actor=request.user)
        except (ValidationError, AvitoAPIError) as exc:
            form.add_error(None, _error_text(exc))
        else:
            messages.success(request, "Объявление перепривязано. Его Avito ID сохранён.")
            return redirect("integrations:connections")
    return render(request, "integrations/rebind.html", {"connection": connection, "form": form, "query": query})


def product_avito_context(product, product_kind, user):
    profile = get_or_create_profile(product, product_kind)
    try:
        connection = profile.connection
    except AvitoListingConnection.DoesNotExist:
        connection = None
    return {
        "avito_profile": profile,
        "avito_connection": connection,
        "avito_profile_form": AvitoProfileForm(instance=profile),
        "avito_photo_form": AvitoPhotoForm(),
        "avito_global_stock": global_stock(profile),
        "can_manage_avito": user.is_superuser or user.has_perm("integrations.manage_avito_product"),
    }


def _product_and_profile(product_kind, pk):
    model = CD if product_kind == "cd" else Tech if product_kind == "tech" else None
    if model is None:
        raise ValidationError("Некорректный тип товара.")
    product = get_object_or_404(model.objects.active(), pk=pk)
    return product, get_or_create_profile(product, product_kind)


@require_POST
@permission_required_any("integrations.manage_avito_product")
def product_profile_save(request, product_kind, pk):
    product, profile = _product_and_profile(product_kind, pk)
    form = AvitoProfileForm(request.POST, instance=profile)
    if form.is_valid():
        try:
            update_profile(profile=profile, data=form.cleaned_data, actor=request.user)
        except (ValidationError, AvitoAPIError) as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Настройки Avito сохранены; синхронизация поставлена в очередь.")
    else:
        messages.error(request, "Проверьте поля Avito: " + " ".join(sum(form.errors.values(), [])))
    return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)


@require_POST
@permission_required_any("integrations.manage_avito_product")
def product_photo_add(request, product_kind, pk):
    product, profile = _product_and_profile(product_kind, pk)
    form = AvitoPhotoForm(request.POST, request.FILES)
    if form.is_valid():
        with transaction.atomic():
            photo = form.save(commit=False)
            photo.profile = profile
            photo.sort_order = (profile.photos.order_by("-sort_order").values_list("sort_order", flat=True).first() or -1) + 1
            photo.save()
            enqueue_profile_sync_after_commit(profile.pk)
        messages.success(request, "Фотография добавлена.")
    else:
        messages.error(request, " ".join(sum(form.errors.values(), [])))
    return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)


@require_POST
@permission_required_any("integrations.manage_avito_product")
def product_photo_delete(request, product_kind, pk, photo_id):
    product, profile = _product_and_profile(product_kind, pk)
    photo = get_object_or_404(AvitoProductPhoto, pk=photo_id, profile=profile)
    with transaction.atomic():
        storage, name = photo.image.storage, photo.image.name
        photo.delete()
        transaction.on_commit(lambda: storage.delete(name))
        enqueue_profile_sync_after_commit(profile.pk)
    messages.success(request, "Фотография удалена.")
    return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)


@require_POST
@permission_required_any("integrations.manage_avito_product")
def product_photo_move(request, product_kind, pk, photo_id):
    product, profile = _product_and_profile(product_kind, pk)
    photo = get_object_or_404(AvitoProductPhoto, pk=photo_id, profile=profile)
    direction = request.POST.get("direction")
    ordered = list(profile.photos.order_by("sort_order", "id"))
    index = ordered.index(photo)
    target_index = index - 1 if direction == "up" else index + 1
    if 0 <= target_index < len(ordered):
        ordered[index], ordered[target_index] = ordered[target_index], ordered[index]
        with transaction.atomic():
            AvitoProductPhoto.objects.filter(profile=profile).update(sort_order=F("sort_order") + 1000)
            for order, item in enumerate(ordered):
                AvitoProductPhoto.objects.filter(pk=item.pk).update(sort_order=order)
            enqueue_profile_sync_after_commit(profile.pk)
    return redirect(f"nomenclature:{product_kind}_detail", pk=product.pk)
