"""Настройки только superuser; сотрудник видит лишь собственную привязку."""
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, ProgrammingError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from accounts.views import superuser_required
from .access import issue_link, set_employee_access
from .client import TelegramClient, TelegramError
from .configuration import TEST_MESSAGE, read_token, save_token, token_configured, expected_status
from .forms import StaffBotForm
from .models import StaffBot, StaffBotAccess, StaffBotJob
from .monitoring import ERROR_LABELS

logger = logging.getLogger('gamebat.business')


def _stub(request):
    return render(request, 'telegram_bots/stub.html', {'notice': TEST_MESSAGE})


@sensitive_post_parameters('token')
@superuser_required
@never_cache
@require_http_methods(['GET', 'POST'])
def dashboard(request):
    if settings.GAMEBAT_ENV == 'local_test':
        return _stub(request)
    try:
        bot = StaffBot.objects.filter(code='staff').first()
    except (OperationalError, ProgrammingError):
        return render(request, 'telegram_bots/stub.html', {'notice': 'Telegram ещё не установлен. Требуется согласованная миграция базы.'}, status=503)
    bot = bot or StaffBot()
    form = StaffBotForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'save' else None, instance=bot)
    employee_link = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save' and form.is_valid():
            try:
                if form.cleaned_data.get('token'):
                    save_token(form.cleaned_data['token'])
                form.save()
                logger.info('telegram_config_saved actor=%s enabled=%s', request.user.pk, bot.enabled)
                messages.success(request, 'Настройки сохранены. Сообщения сотрудникам не отправлялись.')
                return redirect('telegram_bots:dashboard')
            except (OSError, ValidationError):
                form.add_error(None, 'Не удалось сохранить защищённый токен. Проверьте права на файл.')
        elif action == 'check' and bot.pk:
            client = None
            try:
                client = TelegramClient(read_token())
                me = client.call('getMe')
                if not isinstance(me, dict) or str(me.get('username', '')).lower() != bot.username.lower():
                    raise TelegramError('wrong_bot')
                webhook = client.call('getWebhookInfo')
                if not isinstance(webhook, dict) or webhook.get('url'):
                    raise TelegramError('webhook')
                messages.success(request, 'Бот распознан. Webhook не установлен. Сообщения не отправлялись.')
            except (TelegramError, ValidationError) as exc:
                messages.error(request, ERROR_LABELS.get(getattr(exc, 'category', ''), 'Не удалось проверить подключение. Проверьте защищённый токен.'))
            finally:
                if client:
                    client.close()
            return redirect('telegram_bots:dashboard')
        elif action in ['allow', 'revoke'] and bot.pk:
            user = get_object_or_404(get_user_model(), pk=request.POST.get('user_id'))
            set_employee_access(request.user, bot, user, action == 'allow')
            logger.info('telegram_access_changed actor=%s employee=%s allowed=%s', request.user.pk, user.pk, action == 'allow')
            messages.success(request, 'Доступ сотрудника обновлён.')
            return redirect('telegram_bots:dashboard')
        elif action == 'link' and bot.pk:
            user = get_object_or_404(get_user_model(), pk=request.POST.get('user_id'))
            try:
                employee_link = issue_link(user, bot)
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
    accesses = list(StaffBotAccess.objects.filter(bot=bot).select_related('user')) if bot.pk else []
    by_user = {row.user_id: row for row in accesses}
    employees = [{'user': user, 'access': by_user.get(user.pk),
                  'can_price': user.has_perm('price.generate_wholesale_price')}
                 for user in get_user_model().objects.order_by('username')]
    from integrations.worker_models import WorkerService
    from integrations.worker_monitoring import STATUS_LABELS
    worker = WorkerService.objects.filter(code='telegram_staff').first()
    response = render(request, 'telegram_bots/dashboard.html', {'bot': bot, 'form': form,
        'token_configured': token_configured(), 'expected': expected_status(), 'employees': employees,
        'employee_link': employee_link,
        'linked_count': sum(bool(a.telegram_user_id) and a.allowed for a in accesses),
        'worker_label': STATUS_LABELS.get(worker.status, 'Нет данных') if worker else 'Не запущен',
        'connection_error': ERROR_LABELS.get(bot.error_category, bot.error_category),
        'jobs': StaffBotJob.objects.filter(bot=bot).select_related('access__user', 'warehouse')[:30] if bot.pk else []})
    response['Referrer-Policy'] = 'same-origin'
    return response


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def connection(request):
    if not request.user.is_active:
        raise PermissionDenied
    if settings.GAMEBAT_ENV == 'local_test':
        return _stub(request)
    try:
        bot = StaffBot.objects.filter(code='staff').first()
        access = StaffBotAccess.objects.filter(bot=bot, user=request.user).first() if bot else None
    except (OperationalError, ProgrammingError):
        bot = access = None
    link, error = '', ''
    if request.method == 'POST':
        try:
            if not bot:
                raise ValidationError('Бот ещё не настроен администратором.')
            link = issue_link(request.user, bot)
        except ValidationError as exc:
            error = exc.messages[0]
    response = render(request, 'telegram_bots/connection.html', {'bot': bot, 'access': access, 'link': link, 'error': error})
    response['Referrer-Policy'] = 'same-origin'
    return response
