"""Административные страницы ставят задания, но не формируют архив в HTTP."""
from datetime import timedelta
import io
import json
import re
import uuid
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction,OperationalError,ProgrammingError
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from accounts.views import superuser_required
from core.external_policy import require_live_operation
from sales.models import PrintAgent
from .devices import issue_enrollment,revoke
from .forms import ConfigurationForm
from .jobs import request_job,audit,locked_config
from .models import BackupConfiguration,BackupJob,BackupDevice,BackupEvent,PrintRouting
from .window import current_window

STATES={'queued':'Ожидает','snapshot':'Снимок БД','files':'Копируются файлы','checking':'Проверяется согласованность',
    'encrypting':'Шифруется','ready':'Ожидает устройство','downloading':'Скачивается','verified':'Сохранено на устройстве',
    'error':'Ошибка','skipped':'Пропущено','expired':'Удалён с сервера'}
ERRORS={'TimeoutError':'Превышено короткое окно снимка. Проверьте объём и доступность файлов.',
    'pending_queue_full':'Снимок пропущен: устройство ещё не забрало прежние архивы.',
    'ValueError':'Не пройдена проверка состава, ключей или целостности. Неполный архив не опубликован.',
    'OSError':'Ошибка диска или недостаточно свободного места.',
    'OperationalError':'База занята или операция SQLite прервана. Снимок не подтверждён.',
    'interrupted_review_required':'Исполнитель был прерван. Проверьте состояние перед новой заявкой.'}


def stub(request):
    return render(request,'crm_backups/stub.html',{'notice':'ТЕСТОВЫЙ РЕЖИМ: настоящие устройства и рабочие архивы недоступны.'})


@superuser_required
@never_cache
@require_http_methods(['GET','POST'])
def dashboard(request):
    if settings.GAMEBAT_ENV=='local_test':return stub(request)
    try:config=BackupConfiguration.objects.filter(pk=1).first() or BackupConfiguration()
    except (OperationalError,ProgrammingError):
        return render(request,'crm_backups/stub.html',{'notice':'Резервирование ещё не установлено. Требуется согласованная миграция.'},status=503)
    form=ConfigurationForm(request.POST if request.method=='POST' and request.POST.get('action')=='save' else None,instance=config)
    if request.method=='POST':
        try:
            require_live_operation('backup_administration')
            if request.POST.get('action')=='save' and form.is_valid():
                with transaction.atomic():
                    locked_config();saved=form.save();audit('configuration_saved',actor=request.user,
                        enabled=saved.enabled,timezone=saved.timezone,schedule=str(saved.schedule_time))
                messages.success(request,'Настройки сохранены. Приватный ключ сервер не получает.')
                return redirect('crm_backups:dashboard')
            if request.POST.get('action')=='create':
                job=request_job(uuid.UUID(request.POST['request_id']),actor=request.user)
                messages.success(request,'Задание поставлено: '+str(job.pk));return redirect('crm_backups:dashboard')
        except (ValidationError,ValueError,KeyError) as exc:messages.error(request,'Не удалось выполнить действие. '+(' '.join(exc.messages) if isinstance(exc,ValidationError) else 'Проверьте настройки.'))
    window=current_window();jobs=list(BackupJob.objects.all()[:100])
    for job in jobs:
        phase=window['phase'] if window and window['job']==str(job.pk) else job.state
        job.state_label=STATES.get(phase,phase)
        job.error_label=ERRORS.get(job.error,job.error or '—')
    worker_ok=bool(config.last_worker_at and config.last_worker_at>timezone.now()-timedelta(seconds=90))
    notices=[]
    last_saved=BackupJob.objects.filter(state__in=['verified','expired']).order_by('-downloaded_at').first()
    if config.enabled:
        if not last_saved or not last_saved.downloaded_at or last_saved.downloaded_at<timezone.now()-timedelta(days=2):
            notices.append('Нет подтверждённой загрузки на устройство за последние два дня.')
        if jobs and jobs[0].state in ('error','skipped'):notices.append('Последняя попытка не завершена успешно. Проверьте журнал.')
    return render(request,'crm_backups/dashboard.html',{'form':form,'config':config,'jobs':jobs,
        'request_id':uuid.uuid4(),'device':BackupDevice.objects.filter(active_slot=1).first(),
        'events':BackupEvent.objects.select_related('actor').order_by('-pk')[:100],'worker_ok':worker_ok,
        'notices':notices,'last_saved':last_saved})


@sensitive_post_parameters('registration')
@superuser_required
@never_cache
@require_http_methods(['GET','POST'])
def devices(request):
    if settings.GAMEBAT_ENV=='local_test':return stub(request)
    code=''
    try:
        if request.method=='POST':
            require_live_operation('local_devices_administration')
            action=request.POST.get('action')
            if action=='enroll':
                replace=request.POST.get('replace')=='yes'
                code=issue_enrollment(request.user,replace=replace,can_request=request.POST.get('can_request')=='on')
            elif action=='revoke':
                if request.POST.get('confirm')!='yes':raise ValueError
                revoke(request.user,uuid.UUID(request.POST['device_id']));messages.success(request,'Доступ устройства отозван.')
            elif action=='register_printer':
                data=json.loads(request.POST.get('registration','')[:4097])
                if set(data)!={'id','name','printer_name','token_hash'} or not re.fullmatch('[a-f0-9]{64}',data['token_hash']):raise ValueError
                identifier=uuid.UUID(data['id'])
                if not 1<=len(data['name'])<=120 or not 1<=len(data['printer_name'])<=200:raise ValueError
                with transaction.atomic():
                    locked_config()
                    if PrintAgent.objects.filter(pk=identifier).exists():raise ValidationError('Этот профиль уже зарегистрирован. Для ротации используйте штатную процедуру Print Agent.')
                    agent=PrintAgent.objects.create(pk=identifier,name=data['name'],printer_name=data['printer_name'],token_hash=data['token_hash'])
                    audit('printer_registered',actor=request.user,device=str(agent.pk))
                messages.success(request,'Новый агент печати зарегистрирован. Рабочий принтер не переключён.')
            elif action=='default_printer':
                agent=get_object_or_404(PrintAgent,pk=uuid.UUID(request.POST['agent_id']),enabled=True)
                with transaction.atomic():
                    locked_config();route,_=PrintRouting.objects.get_or_create(pk=1)
                    route.default_agent=agent;route.save();audit('default_printer_changed',actor=request.user,device=str(agent.pk))
                messages.success(request,'Назначение новых заданий сохранено. Прежние задания сохраняют свою цель.')
            elif action=='disable_printer':
                if request.POST.get('confirm')!='yes':raise ValueError
                identifier=uuid.UUID(request.POST['agent_id'])
                call_command('register_print_agent',disable=identifier,stdout=io.StringIO())
                audit('printer_disabled',actor=request.user,device=str(identifier))
            else:raise ValueError
    except (ValueError,TypeError,KeyError,ValidationError,PermissionError):messages.error(request,'Действие отклонено. Проверьте поля и явное подтверждение замены/отзыва.')
    try:
        printers=list(PrintAgent.objects.all());device=BackupDevice.objects.filter(active_slot=1).first()
        route=PrintRouting.objects.filter(pk=1).first()
    except (OperationalError,ProgrammingError):
        return render(request,'crm_backups/stub.html',{'notice':'Требуется согласованная миграция локальных приложений.'},status=503)
    return render(request,'crm_backups/devices.html',{'printers':printers,'device':device,'code':code,'route':route})
