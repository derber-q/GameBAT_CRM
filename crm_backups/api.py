"""Узкий машинный API: Bearer, loopback/HTTPS, UUID; никаких произвольных путей."""
from datetime import timedelta
from functools import wraps
import hashlib
import hmac
import json
import re
import uuid
from urllib.parse import urlsplit
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction, OperationalError, IntegrityError
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from core.external_policy import require_live_operation
from .models import BackupDevice, BackupJob, BackupConfiguration
from .devices import enroll
from .jobs import request_job, archive_path, audit


class APIError(Exception):
    def __init__(self, code, status=400): self.code,self.status=code,status


def device_api(method, *, registration=False):
    def decorate(function):
        @csrf_exempt
        @never_cache
        @require_http_methods([method])
        @wraps(function)
        def view(request, **kwargs):
            try:
                require_live_operation('backup_api')
                host=urlsplit('//'+request.get_host()).hostname
                if request.headers.get('Origin') or (not request.is_secure() and not (
                    settings.GAMEBAT_ENV=='local_live' and host in ('localhost','127.0.0.1','::1'))):
                    raise APIError('secure_connection_required',403)
                data={}
                if method=='POST':
                    if request.content_type!='application/json' or len(request.body)>4096: raise APIError('invalid_json')
                    data=json.loads(request.body or b'{}')
                    if not isinstance(data,dict): raise APIError('invalid_json')
                device=None
                if not registration:
                    auth=request.headers.get('Authorization','')
                    token=auth[7:] if auth.startswith('Bearer ') else ''
                    if not 32<=len(token)<=256: raise APIError('unauthorized',401)
                    device=BackupDevice.objects.filter(pk=uuid.UUID(request.headers.get('X-Backup-Device','')),active_slot=1).first()
                    if not device or not hmac.compare_digest(device.token_hash,hashlib.sha256(token.encode()).hexdigest()):
                        raise APIError('unauthorized',401)
                    session=uuid.UUID(request.headers.get('X-Backup-Session',''))
                    if function.__name__!='heartbeat' and device.session!=session:
                        raise APIError('session_conflict',409)
                    request.backup_session=session
                return function(request,device,data,**kwargs)
            except APIError as exc: return JsonResponse({'error':exc.code},status=exc.status)
            except (ValueError,KeyError,TypeError): return JsonResponse({'error':'invalid_request'},status=400)
            except ValidationError: return JsonResponse({'error':'operation_blocked'},status=403)
            except PermissionError: return JsonResponse({'error':'permission_revoked'},status=403)
            except BackupDevice.DoesNotExist: return JsonResponse({'error':'unauthorized'},status=401)
            except IntegrityError:return JsonResponse({'error':'registration_conflict'},status=409)
            except (OperationalError,): return JsonResponse({'error':'database_busy'},status=503)
            except Exception:
                # DEBUG рабочей локальной CRM не должен раскрывать Bearer/код
                # регистрации в технической странице исключения.
                return JsonResponse({'error':'internal_error'},status=500)
        return view
    return decorate


@device_api('POST',registration=True)
def registration(request,device,data):
    result=enroll(data['code'],data['device_id'],data['token_hash'],data['name'])
    return JsonResponse({'device_id':str(result.pk),'protocol':1})


@device_api('POST')
@transaction.atomic
def heartbeat(request,device,data):
    # Запись в единственную конфигурацию сериализует смену сессии на SQLite.
    from .jobs import locked_config
    locked_config()
    device=BackupDevice.objects.select_for_update().get(pk=device.pk,active_slot=1)
    if device.session and device.session!=request.backup_session and device.last_seen_at and device.last_seen_at>timezone.now()-timedelta(seconds=90):
        raise APIError('session_conflict',409)
    device.session=request.backup_session; device.last_seen_at=timezone.now()
    device.version=str(data.get('version','1'))[:32]
    device.save(update_fields=['session','last_seen_at','version'])
    return JsonResponse({'ok':True,'can_request':device.can_request,'protocol':1})


def metadata(job):
    return {'id':str(job.pk),'state':job.state,'size':job.size,'sha256':job.sha256,'key_id':job.key_id,
        'snapshot_at':job.metadata.get('snapshot_at'), 'version':job.metadata.get('sha',''),
        'environment_id':job.metadata.get('environment_id',''), 'database_engine':job.metadata.get('database_engine',''),
        'kind':job.kind, 'error':job.error}


@device_api('GET')
def status(request,device,data):
    return JsonResponse({'jobs':[metadata(job) for job in BackupJob.objects.exclude(state='expired').order_by('-created_at')[:100]]})


@device_api('POST')
def create(request,device,data):
    if not device.can_request: raise APIError('manual_request_forbidden',403)
    return JsonResponse(metadata(request_job(uuid.UUID(data['request_id']))))


def _job(pk):
    config=BackupConfiguration.objects.get(pk=1)
    job=BackupJob.objects.filter(pk=pk,metadata__environment_id=str(config.environment_id),state__in=('ready','downloading','verified')).first()
    if not job: raise APIError('archive_unavailable',404)
    return job


@device_api('GET')
def download(request,device,data,pk):
    job=_job(pk); path=archive_path(job)
    if not path.is_file() or path.is_symlink() or path.stat().st_nlink!=1 or path.stat().st_size!=job.size:
        raise APIError('archive_unavailable',404)
    etag='"'+job.sha256+'"'
    if request.headers.get('If-Match') not in (None,etag): raise APIError('archive_changed',412)
    start=0
    if raw:=request.headers.get('Range'):
        match=re.fullmatch(r'bytes=(\d+)-',raw)
        if not match or request.headers.get('If-Match')!=etag: raise APIError('range_requires_etag',416)
        start=int(match[1])
        if not 0<=start<job.size: raise APIError('invalid_range',416)
    if job.state=='ready':
        job.state='downloading';job.save(update_fields=['state'])
    def chunks():
        with path.open('rb') as stream:
            stream.seek(start)
            while block:=stream.read(1024*1024):
                # Отзыв действует и на длинную передачу; хеш/сессия не меняются незаметно.
                if not BackupDevice.objects.filter(pk=device.pk,active_slot=1,token_hash=device.token_hash,session=device.session).exists(): return
                yield block
    response=StreamingHttpResponse(chunks(),status=206 if start else 200,content_type='application/octet-stream')
    response['Content-Length']=str(job.size-start); response['Accept-Ranges']='bytes'; response['ETag']=etag
    response['Content-Disposition']=f'attachment; filename="{job.pk}.backup"'
    if start: response['Content-Range']=f'bytes {start}-{job.size-1}/{job.size}'
    audit('archive_download_started',job=job,device=str(device.pk),offset=start)
    return response


@device_api('POST')
@transaction.atomic
def confirm(request,device,data,pk):
    job=_job(pk)
    if type(data.get('size')) is not int or data['size']!=job.size or data.get('sha256')!=job.sha256:
        raise APIError('verification_failed')
    job.state='verified'; job.downloaded_at=timezone.now(); job.save(update_fields=['state','downloaded_at'])
    audit('archive_device_verified',job=job,device=str(device.pk))
    return JsonResponse({'ok':True})
