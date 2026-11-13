from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_POST
from core.decorators import permission_required_any
from partners.models import Partner
from .models import Customer, BotConfig, OrderIntent, Event, Delivery, Audit
from .forms import ConfigurationForm
from .services import authorize, require, set_service_state


@require_POST
@permission_required_any('wholesale_bot.configure_wholesale_bot')
def service_state(request):
    try:
        value = request.POST.get('accepting')
        if value not in ('on', 'off'):
            raise ValidationError('Выберите включение или выключение приёма заказов.')
        config = set_service_state(actor=request.user, accepting=value == 'on', revision=request.POST.get('revision'))
        messages.success(request, ('Приём заказов включён.' if config.accepting_orders else 'Приём заказов выключен.')
                         + ' Уведомления авторизованным покупателям поставлены в очередь.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('price:index')


@require_GET
@permission_required_any('wholesale_bot.manage_wholesale_customers')
def dashboard(request):
    require(request.user, 'wholesale_bot.manage_wholesale_customers')
    customers = Customer.objects.select_related('partner', 'approved_by').order_by('-requested_at', '-pk')
    state = request.GET.get('status', '')
    if state in Customer.Status.values:
        customers = customers.filter(status=state)
    config = BotConfig.objects.filter(pk=1).first()
    return render(request, 'wholesale_bot/dashboard.html', {
        'customers': Paginator(customers, 40).get_page(request.GET.get('page')),
        'statuses': Customer.Status.choices, 'status': state,
        'partners': Partner.objects.filter(is_archived=False), 'config': config,
        'orders': OrderIntent.objects.select_related('sale', 'partner', 'customer').order_by('-created_at')[:40],
        'deliveries': Delivery.objects.select_related('customer', 'intent').filter(state__in=['error', 'uncertain']).order_by('-pk')[:40],
        'events': Event.objects.select_related('customer').filter(state='error').order_by('-pk')[:40],
        'audits': Audit.objects.select_related('actor', 'customer').order_by('-pk')[:40],
    })


@require_POST
@permission_required_any('wholesale_bot.manage_wholesale_customers')
def customer_action(request, pk):
    try:
        authorize(actor=request.user, customer_id=pk, revision=request.POST.get('revision'),
                  action=request.POST.get('action'), partner_id=request.POST.get('partner') or None)
        messages.success(request, 'Доступ сохранён. Уведомление поставлено в очередь.')
    except (ValidationError, Customer.DoesNotExist) as exc:
        messages.error(request, '; '.join(getattr(exc, 'messages', ['Покупатель не найден.'])))
    return redirect('wholesale_bot:dashboard')


@permission_required_any('wholesale_bot.configure_wholesale_bot')
def configuration(request):
    require(request.user, 'wholesale_bot.configure_wholesale_bot')
    # GET не создаёт конфигурацию и не делает сетевых вызовов.
    config = BotConfig.objects.filter(pk=1).first() or BotConfig()
    form = ConfigurationForm(request.POST if request.method == 'POST' else None, instance=config)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            Audit.objects.create(actor=request.user, kind='configuration_saved')
        messages.success(request, 'Настройки сохранены. Токен устанавливается отдельной локальной командой.')
        return redirect('wholesale_bot:configuration')
    response = render(request, 'wholesale_bot/configuration.html', {'form': form, 'config': config})
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@permission_required_any('wholesale_bot.manage_wholesale_customers')
def retry(request, kind, pk):
    require(request.user, 'wholesale_bot.manage_wholesale_customers')
    if kind not in ('event', 'delivery'):
        from django.http import Http404
        raise Http404()
    model = Delivery if kind == 'delivery' else Event
    with transaction.atomic():
        row = get_object_or_404(model.objects.select_for_update(), pk=pk)
        if row.state in ('error', 'uncertain'):
            row.state, row.error = 'pending', ''
            row.save(update_fields=['state', 'error'])
            Audit.objects.create(actor=request.user, customer=row.customer, kind='retry_' + kind, detail=f'id={pk}')
    messages.success(request, 'Повтор поставлен в очередь. Уже созданная продажа повторно не оформляется.')
    return redirect('wholesale_bot:dashboard')


@require_GET
@permission_required_any('wholesale_bot.manage_wholesale_customers')
def original(request, pk):
    require(request.user, 'wholesale_bot.manage_wholesale_customers')
    intent = get_object_or_404(OrderIntent, pk=pk)
    response = HttpResponse(bytes(intent.content), content_type='application/octet-stream')
    response['Content-Disposition'] = content_disposition_header(True, f'order-{intent.pk}.xlsx')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
