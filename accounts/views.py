import logging
import mimetypes
from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import AdminPasswordResetForm, CRMUserCreationForm, CRMUserUpdateForm, PermissionSetForm
from .models import User

logger = logging.getLogger("gamebat.business")


def superuser_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("У вас нет доступа к управлению пользователями.")
        return view_func(request, *args, **kwargs)
    return wrapped


@superuser_required
def user_list(request):
    return render(request, "accounts/user_list.html", {"users": User.objects.prefetch_related("groups")})


@superuser_required
def user_detail(request, pk):
    target = get_object_or_404(User.objects.prefetch_related("groups", "user_permissions"), pk=pk)
    return render(request, "accounts/user_detail.html", {"target": target})


@superuser_required
def user_create(request):
    form = CRMUserCreationForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        logger.info("Пользователь создан: actor_id=%s user_id=%s", request.user.pk, user.pk)
        messages.success(request, "Пользователь создан.")
        return redirect("accounts:user_detail", pk=user.pk)
    return render(request, "accounts/form.html", {"form": form, "title": "Создать пользователя"})


@superuser_required
def user_update(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = CRMUserUpdateForm(request.POST or None, request.FILES or None, instance=target)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        logger.info("Права и профиль изменены: actor_id=%s user_id=%s", request.user.pk, user.pk)
        messages.success(request, "Данные и права сохранены.")
        return redirect("accounts:user_detail", pk=user.pk)
    return render(request, "accounts/form.html", {"form": form, "title": "Редактировать пользователя"})


@superuser_required
def admin_password_reset(request, pk):
    target = get_object_or_404(User, pk=pk)
    form = AdminPasswordResetForm(target, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        logger.info("Пароль сброшен администратором: actor_id=%s user_id=%s", request.user.pk, target.pk)
        messages.success(request, "Новый пароль установлен.")
        return redirect("accounts:user_detail", pk=target.pk)
    return render(request, "accounts/form.html", {"form": form, "title": f"Сбросить пароль: {target.username}"})


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Пароль изменён.")
        return redirect("core:home")
    return render(request, "accounts/form.html", {"form": form, "title": "Сменить пароль"})


@login_required
def verification_document(request, pk):
    target = get_object_or_404(User, pk=pk)
    if request.user != target and not (request.user.is_superuser or request.user.has_perm("accounts.view_user_document")):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("У вас нет доступа к этому документу.")
    if not target.verification_document:
        raise Http404("Документ не загружен.")
    try:
        file_handle = target.verification_document.storage.open(target.verification_document.name, "rb")
    except FileNotFoundError as exc:
        raise Http404("Файл не найден.") from exc
    content_type = mimetypes.guess_type(target.verification_document.name)[0] or "application/octet-stream"
    return FileResponse(file_handle, content_type=content_type, filename=target.verification_document.name.rsplit("/", 1)[-1])


@superuser_required
def permission_set_list(request):
    return render(request, "accounts/permission_set_list.html", {"groups": Group.objects.prefetch_related("permissions")})


@superuser_required
def permission_set_edit(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else Group()
    form = PermissionSetForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        logger.info("Набор прав сохранён: actor_id=%s group_id=%s", request.user.pk, saved.pk)
        messages.success(request, "Набор прав сохранён.")
        return redirect("accounts:permission_sets")
    return render(request, "accounts/form.html", {"form": form, "title": "Набор прав"})


@require_POST
@superuser_required
def permission_set_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    logger.info("Набор прав удалён: actor_id=%s group_id=%s", request.user.pk, pk)
    messages.success(request, "Набор прав удалён.")
    return redirect("accounts:permission_sets")
