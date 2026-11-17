"""Закрытая панель магазина: закупочные поля доступны только разрешённым сотрудникам."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.utils import timezone
from core.decorators import permission_required_all
from digital_prices.api import APIError, parse_page
from digital_sales.parser import money
from digital_prices.models import Product
from digital_sales.models import BuyerBalanceChat
from .models import ShopConfig, ShopChat, PurchaseIntent, ResultDelivery, AuditEvent
from .forms import ConfigurationForm, DiscoveryForm
from .admin_services import configure, set_chat, discover, rescan, map_legacy, confirm_refund
from .telegram import provider_client


@never_cache
@permission_required_all('digital_shop.manage_shop', 'digital_prices.view_cost')
@require_http_methods(['GET', 'POST'])
def dashboard(request):
    config, _ = ShopConfig.objects.get_or_create(pk=1)
    form = ConfigurationForm(initial={'revision': config.revision, 'enabled': config.enabled,
        'purchases_enabled': config.purchases_enabled, 'supplier': config.supplier_id})
    discovery = DiscoveryForm()
    found = []
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'configure':
                form = ConfigurationForm(request.POST)
                if form.is_valid():
                    configure(actor=request.user, **form.cleaned_data)
                    messages.success(request, 'Настройки магазина сохранены.')
                    return redirect('digital_shop:dashboard')
            elif action == 'chat':
                set_chat(actor=request.user, binding_id=request.POST.get('chat'), enabled=request.POST.get('enabled') == '1')
                return redirect('digital_shop:dashboard')
            elif action == 'balance':
                api = provider_client()
                try:
                    response = api.balance()
                    if response.get('currency', '').upper() != 'RUB':
                        raise APIError('currency')
                    config.observed_balance, config.observed_at = money(response.get('balance')), timezone.now()
                    config.save(update_fields=['observed_balance', 'observed_at'])
                    AuditEvent.objects.create(actor=request.user, kind='balance_observed')
                finally:
                    api.close()
                messages.success(request, 'Внешний снимок получен. Внутренний журнал не изменён.')
                return redirect('digital_shop:dashboard')
            elif action in ('search', 'discover'):
                discovery = DiscoveryForm(request.POST)
                api = provider_client()
                try:
                    if action == 'search' and discovery.is_valid():
                        data = discovery.cleaned_data
                        response = api.search(data['query'], platform=data['platform'], region=data['region'] or None)
                        found, _ = parse_page({'items': response.get('items'), 'page': 1, 'has_more': False}, 1)
                    elif action == 'discover':
                        payload = api.product(request.POST.get('product_id'))
                        rows, _ = parse_page({'items': [payload], 'page': 1, 'has_more': False}, 1)
                        product = discover(actor=request.user, offer=rows[0])
                        editions = payload.get('editions', [])
                        if isinstance(editions, list) and editions:
                            found, _ = parse_page({'items': editions[:50], 'page': 1, 'has_more': False}, 1)
                        messages.success(request, f'Карточка №{product.pk} сохранена. До назначения наценки она скрыта от покупателей.')
                finally:
                    api.close()
            elif action == 'rescan':
                rescan(actor=request.user, intent_id=request.POST.get('intent'))
                messages.success(request, 'Назначена сверка прежнего заказа; новый идентификатор покупки не создаётся.')
                return redirect('digital_shop:dashboard')
            elif action == 'map':
                if request.POST.get('confirmed') != 'yes':
                    raise ValidationError('Нужно подтвердить соответствие характеристик.')
                map_legacy(actor=request.user, old_id=request.POST.get('old_id'), new_id=request.POST.get('new_id'))
                messages.success(request, 'Привязка подтверждена; старые карточки и наценки сохранены.')
                return redirect('digital_shop:dashboard')
            elif action == 'refund':
                if request.POST.get('confirmed') != 'yes':
                    raise ValidationError('Нужно явное подтверждение фактического возврата.')
                confirm_refund(actor=request.user, line_id=request.POST.get('line'), reason=request.POST.get('reason'))
                messages.success(request, 'Подтверждённый возврат учтён, резерв позиции освобождён.')
                return redirect('digital_shop:dashboard')
            else:
                raise ValidationError('Неизвестное действие.')
        except (ValidationError, APIError, ValueError, Product.DoesNotExist):
            messages.error(request, 'Действие не выполнено. Проверьте поля, доступ к интеграции и состояние заказа. Подробности ответа поставщика скрыты.')
    enabled = set(ShopChat.objects.filter(enabled=True).values_list('binding_id', flat=True))
    chats = [{'row': row, 'enabled': row.pk in enabled} for row in BuyerBalanceChat.objects.filter(buyer__isnull=False).select_related('buyer')]
    return render(request, 'digital_shop/dashboard.html', {'config': config, 'form': form, 'discovery': discovery, 'found': found,
        'chats': chats, 'orders': PurchaseIntent.objects.select_related('cart__buyer').order_by('-created_at')[:100],
        'deliveries': ResultDelivery.objects.filter(state__in=['review', 'uncertain']).select_related('line__intent', 'buyer'),
        'legacy': Product.objects.filter(external_id__startswith='v1_code_', superseded_by__isnull=True).order_by('source_name'),
        'v2_candidates': Product.objects.filter(api_version=2, source_type='code').order_by('source_name'),
        'audit': AuditEvent.objects.select_related('actor').order_by('-pk')[:30]})


@never_cache
@permission_required_all('digital_shop.manage_shop', 'digital_prices.view_cost')
@sensitive_post_parameters('result')
@require_http_methods(['GET', 'POST'])
def order_detail(request, pk):
    import json
    from digital_sales.services import require
    from digital_sales.crypto import decrypt
    from .admin_services import approve_result, retry_delivery
    order = get_object_or_404(PurchaseIntent.objects.select_related('cart__buyer'), pk=pk)
    revealed = None
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'reveal':
                require(request.user, 'digital_sales.view_digital_secrets')
                revealed = json.dumps(decrypt(order.encrypted_response), ensure_ascii=False, indent=2) if order.encrypted_response else 'Ответ пока не получен.'
                AuditEvent.objects.create(actor=request.user, intent=order, kind='result_revealed')
            elif action in ('approve', 'retry') and request.POST.get('confirmed') == 'yes':
                line = get_object_or_404(order.lines, pk=request.POST.get('line'))
                if action == 'approve':
                    result = json.loads(request.POST.get('result', '{}'), parse_float=__import__('decimal').Decimal)
                    approve_result(actor=request.user, line_id=line.pk, result=result)
                else:
                    delivery = get_object_or_404(ResultDelivery, line=line)
                    retry_delivery(actor=request.user, delivery_id=delivery.pk)
                messages.success(request, 'Подтверждённое действие сохранено.')
                return redirect('digital_shop:order', pk=order.pk)
            else:
                raise ValidationError('Нужно явное подтверждение действия.')
        except (ValidationError, ValueError, KeyError):
            messages.error(request, 'Действие не выполнено. Проверьте состояние и безопасный формат результата.')
    return render(request, 'digital_shop/order.html', {'order': order, 'revealed': revealed})
