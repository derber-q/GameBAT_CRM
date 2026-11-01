"""Короткая проверка версии/БД/worker для менеджера, без внешних API и изменений данных."""
from django.conf import settings
from django.db import connection
from django.http import JsonResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from deployment.version import current_version


@require_GET
@never_cache
def update_health(request):
    if settings.GAMEBAT_ENV!='production':
        raise Http404
    version = current_version(settings.BASE_DIR)['sha']
    ok = False
    try:
        connection.ensure_connection()
        from integrations.worker_monitoring import monitoring_snapshot
        data = monitoring_snapshot()
        ok = bool(version and connection.vendor=='postgresql' and connection.is_usable() and data['mode']=='managed' and data['controller_ok']
                  and all(row['expected']!='required' or row['status']=='running' for row in data['services']))
    except Exception:
        pass
    return JsonResponse({'status':'ok' if ok else 'starting','sha':version,'environment':'production'},status=200 if ok else 503)
