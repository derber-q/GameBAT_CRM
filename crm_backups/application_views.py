from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse,Http404
from django.shortcuts import render,get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import ApplicationArtifact
from .client_apps import artifact_path
from .snapshot import digest


def allowed(user):
    if not user.is_active or not user.has_perm('crm_backups.download_client_apps'):raise PermissionDenied


@login_required
@never_cache
@require_GET
def applications(request):
    allowed(request.user)
    artifacts={} if settings.GAMEBAT_ENV=='local_test' else {a.kind:a for a in ApplicationArtifact.objects.filter(current=True)}
    return render(request,'crm_backups/applications.html',{'agent':artifacts.get('local_agent'),'opera':artifacts.get('opera')})


@login_required
@never_cache
@require_GET
def download(request,pk):
    allowed(request.user)
    if settings.GAMEBAT_ENV=='local_test':raise PermissionDenied
    artifact=get_object_or_404(ApplicationArtifact,pk=pk)
    path=artifact_path(artifact)
    if not path.is_file() or path.is_symlink() or path.stat().st_size!=artifact.size or digest(path)!=artifact.sha256:raise Http404
    prefix='ReSOURCE-Local-Agent' if artifact.kind=='local_agent' else 'ReSOURCE-Avito-Check'
    response=FileResponse(path.open('rb'),as_attachment=True,filename=f'{prefix}-{artifact.version}.zip',content_type='application/zip')
    response['ETag']='"'+artifact.sha256+'"'
    return response
