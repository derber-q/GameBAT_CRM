"""Machine API: только отдельный Bearer, без cookie-аутентификации и CORS."""
from functools import wraps
import hashlib
import hmac
import json
from urllib.parse import urlsplit
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import OperationalError
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

from core.external_policy import require_live_operation
from .models import PrintAgent
from . import print_agents as service


def agent_api(method):
    def decorate(function):
        @csrf_exempt
        @never_cache
        @require_http_methods([method])
        @wraps(function)
        def view(request, **kwargs):
            try:
                require_live_operation('print_agent_api')
                if getattr(settings,'LABEL_PRINT_BACKEND','native')!='agent':
                    raise service.AgentError('agent_backend_disabled',403)
                host = urlsplit('//'+request.get_host()).hostname
                if request.headers.get('Origin') or (not request.is_secure() and not (
                        settings.GAMEBAT_ENV=='local_live' and host in ('127.0.0.1','localhost','::1'))):
                    raise service.AgentError('secure_agent_connection_required',403)
                if request.headers.get('X-Print-Protocol') != '1':
                    raise service.AgentError('unsupported_protocol',409)
                try:
                    agent_id=uuid.UUID(request.headers.get('X-Print-Agent',''))
                    instance=uuid.UUID(request.headers.get('X-Print-Session',''))
                except ValueError:
                    raise service.AgentError('unauthorized',401) from None
                auth=request.headers.get('Authorization','')
                token=auth[7:] if auth.startswith('Bearer ') else ''
                agent=PrintAgent.objects.filter(pk=agent_id,enabled=True).first()
                digest=hashlib.sha256(token.encode()).hexdigest()
                if not hmac.compare_digest(digest,agent.token_hash if agent else '0'*64) or not token:
                    raise service.AgentError('unauthorized',401)
                data={}
                if method=='POST':
                    if request.content_type!='application/json' or len(request.body)>4096:
                        raise service.AgentError('invalid_json',400)
                    data=json.loads(request.body or b'{}')
                    if not isinstance(data,dict):
                        raise service.AgentError('invalid_json',400)
                return function(request,agent_id,instance,data,**kwargs)
            except service.AgentError as error:
                return JsonResponse({'error':error.code},status=error.status)
            except (ValueError,TypeError,json.JSONDecodeError):
                return JsonResponse({'error':'invalid_request'},status=400)
            except ValidationError:
                return JsonResponse({'error':'operation_blocked'},status=403)
            except PermissionDenied:
                return JsonResponse({'error':'permission_revoked'},status=403)
            except PrintAgent.DoesNotExist:
                return JsonResponse({'error':'unauthorized'},status=401)
            except OperationalError:
                return JsonResponse({'error':'database_busy'},status=503)
        return view
    return decorate


@agent_api('POST')
def heartbeat(request,agent_id,instance,data):
    return JsonResponse(service.heartbeat(agent_id,instance,data))


@agent_api('POST')
def claim(request,agent_id,instance,data):
    return JsonResponse(service.claim(agent_id,instance))


@agent_api('POST')
def result(request,agent_id,instance,data,request_id):
    from .models import AvitoShippingPrintJob
    if AvitoShippingPrintJob.objects.filter(request_id=request_id).exists():
        from .avito_shipping import agent_result
        return JsonResponse(agent_result(agent_id,instance,request_id,data))
    return JsonResponse(service.result(agent_id,instance,request_id,data))


@agent_api('GET')
def document(request,agent_id,instance,data,request_id):
    from .models import AvitoShippingPrintJob
    if AvitoShippingPrintJob.objects.filter(request_id=request_id).exists():
        from .avito_shipping import agent_owned
        job=agent_owned(agent_id,instance,request_id)
        if job.state not in service.AGENT_ACTIVE:
            raise service.AgentError('document_unavailable')
        return FileResponse(job.file.open('rb'),content_type='application/pdf',filename=f'label-{job.request_id}.pdf')
    job=service.owned_job(agent_id,instance,request_id)
    if job.state not in service.AGENT_ACTIVE or not job.document_id or not job.document_digest:
        raise service.AgentError('document_unavailable')
    return FileResponse(job.document.file.open('rb'),content_type='application/pdf',filename=f'label-{job.request_id}.pdf')
