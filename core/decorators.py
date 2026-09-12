from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def permission_required_any(*permissions):
    """Проверяет наличие хотя бы одного права и защищает прямой URL."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser or any(request.user.has_perm(p) for p in permissions):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("У вас нет доступа к этому разделу.")
        return wrapped
    return decorator


def permission_required_all(*permissions):
    """Требует все перечисленные права; superuser проходит штатно."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser or all(request.user.has_perm(p) for p in permissions):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("У вас нет доступа к этому действию.")
        return wrapped
    return decorator
