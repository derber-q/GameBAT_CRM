"""Краткое техническое окно: индикация без запроса к заблокированной SQLite."""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse


def marker_path():
    return Path(getattr(settings, 'CRM_BACKUP_ROOT', settings.BASE_DIR / '.local-backup-cache')) / 'window.json'


def publish(job_id, phase):
    path = marker_path()
    value = {'job': str(job_id), 'phase': phase,
             'expires': (datetime.now(timezone.utc) + timedelta(seconds=20)).isoformat()}
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600); json.dump(value, stream)
    os.replace(temporary, path)


def current_window():
    if settings.GAMEBAT_ENV == 'local_test': return None
    try:
        path = marker_path()
        if path.is_symlink() or path.stat().st_size > 1024: return None
        data = json.loads(path.read_text(encoding='utf-8'))
        if datetime.fromisoformat(data['expires']) > datetime.now(timezone.utc) and data['phase']=='snapshot':
            return data
    except (OSError, ValueError, KeyError): pass
    return None


class BackupWindowMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        # Machine print API продолжает отвечать после короткого SQLite-окна;
        # перед окном запрещено наличие начатых физических заданий.
        if request.method not in ('GET','HEAD','OPTIONS') and not request.path.startswith('/crm/print-agent/') and current_window():
            response = JsonResponse({'error': 'backup_window', 'message':
                'Создаётся согласованный снимок CRM. Повторите действие через несколько секунд.'}, status=503)
            response['Retry-After'] = '15'
            return response
        return self.get_response(request)
