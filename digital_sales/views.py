"""Веб-формы цифрового учёта; секреты доступны только явным защищённым POST."""
import base64
import uuid
from django.contrib import messages
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.http import content_disposition_header
from core.decorators import permission_required_all
from .models import (Buyer, Supplier, DigitalBot, DigitalOrder, SupplierMessage,
                     BalanceMovement, BalanceObservation, AuditEvent, Notification)
from . import forms, services
from .ingestion import expected_balance, resolve_order, link_orders, store_manual_goods, correct_checklist, attach_message
from .crypto import decrypt


def _page(request, rows, key, size):
    """Независимая пагинация журналов сохраняет поисковые фильтры страницы."""
    page = Paginator(rows, size).get_page(request.GET.get(key))
    def url(number):
        values = request.GET.copy()
        values[key] = number
        return '?' + values.urlencode()
    page.previous_url = url(page.previous_page_number()) if page.has_previous() else ''
    page.next_url = url(page.next_page_number()) if page.has_next() else ''
    return page


@permission_required_all('digital_sales.view_digital_sales')
@never_cache
@require_http_methods(['GET'])
def dashboard(request):
    orders = DigitalOrder.objects.select_related('buyer', 'supplier', 'sale').prefetch_related('references')
    if request.GET.get('q'):
        query = request.GET['q'][:200]
        orders = orders.filter(Q(buyer__name__icontains=query) | Q(items__icontains=query) | Q(references__number__icontains=query) | Q(sale__visible_id__icontains=query)).distinct()
    if request.GET.get('state') in DigitalOrder.State.values:
        orders = orders.filter(state=request.GET['state'])
    if request.GET.get('buyer', '').isdecimal():
        orders = orders.filter(buyer_id=int(request.GET['buyer']))
    elif request.GET.get('buyer') == 'retail':
        orders = orders.filter(is_retail=True)
    from django.utils.dateparse import parse_date
    for field, lookup in [('from', 'created_at__date__gte'), ('to', 'created_at__date__lte')]:
        try:
            value = parse_date(request.GET.get(field, ''))
        except ValueError:
            value = None
        if value:
            orders = orders.filter(**{lookup: value})
    suppliers = []
    reconciliation = request.user.has_perm('digital_sales.view_digital_reconciliation')
    if reconciliation:
        for supplier in Supplier.objects.all():
            latest = supplier.observations.select_related('message').order_by('-message__occurred_at', '-pk').first()
            suppliers.append({'supplier': supplier, 'expected': expected_balance(supplier), 'latest': latest})
    return render(request, 'digital_sales/dashboard.html', {'orders': _page(request, orders, 'page', 40),
        'states': DigitalOrder.State.choices, 'buyers': Buyer.objects.select_related('balance_chat'), 'suppliers': suppliers,
        'movements': _page(request, BalanceMovement.objects.select_related('buyer', 'supplier', 'sale', 'actor').filter(
            Q() if reconciliation else Q(supplier__isnull=True)).order_by('-pk'), 'movement_page', 100),
        'observations': _page(request, BalanceObservation.objects.select_related('supplier', 'message').order_by('-pk'), 'observation_page', 50) if reconciliation else [],
        'notifications': Notification.objects.select_related('order', 'access__user').order_by('-pk')[:50] if request.user.is_superuser else []})


@permission_required_all('digital_sales.manage_digital_buyers')
@never_cache
@require_http_methods(['GET', 'POST'])
def buyer_edit(request, pk=None):
    buyer = get_object_or_404(Buyer, pk=pk) if pk else None
    form = forms.BuyerForm(request.POST or None, instance=buyer)
    if request.method == 'POST' and form.is_valid():
        services.require(request.user, 'digital_sales.manage_digital_buyers')
        with transaction.atomic():
            result = form.save()
            AuditEvent.objects.create(actor=request.user, kind='buyer_saved', detail=f'buyer={result.pk}')
        return redirect('digital_sales:dashboard')
    return render(request, 'digital_sales/form.html', {'form': form, 'title': 'Цифровой покупатель'})


@permission_required_all('digital_sales.view_digital_sales')
@never_cache
@require_http_methods(['GET', 'POST'])
def balance(request):
    if not request.user.has_perm('digital_sales.topup_digital_balances') and not request.user.has_perm('digital_sales.adjust_digital_balances'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    form = forms.BalanceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            services.move_balance(actor=request.user, buyer_id=data['buyer'].pk if data['buyer'] else None,
                supplier_id=data['supplier'].pk if data['supplier'] else None, amount=data['amount'],
                kind=data['kind'], reason=data['reason'], operation_key=data['operation_key'])
            return redirect('digital_sales:dashboard')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'digital_sales/form.html', {'form': form, 'title': 'Движение цифрового баланса',
        'notice': 'Внутренний учёт уже внесённых средств. Эта форма не создаёт повторного поступления в кассу или банк.'})


@sensitive_post_parameters('secret')
@sensitive_variables()
@permission_required_all('digital_sales.create_digital_sales', 'sales.create_sale')
@never_cache
@require_http_methods(['GET', 'POST'])
def manual(request):
    form = forms.ManualForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            if data['secret']:
                services.require(request.user, 'digital_sales.view_digital_secrets')
            sale = services.manual_sale(actor=request.user, supplier_id=data['supplier'].pk,
                buyer_id=data['buyer'].pk if isinstance(data['buyer'], Buyer) else None,
                is_retail=data['buyer'] == 'retail',
                items=data['items'], price=data['price'], creation_key=data['creation_key'],
                numbers=data['numbers'].replace(';', ',').split(','), secret=data['secret'], comment=data['comment'], source_url=data['source_url'])
            return redirect('digital_sales:order', pk=sale.digital_order.pk)
        except (ValidationError, ImproperlyConfigured) as exc:
            form.add_error(None, '; '.join(getattr(exc, 'messages', [str(exc)])))
    return render(request, 'digital_sales/form.html', {'form': form, 'title': 'Создать цифровую продажу'})


@permission_required_all('digital_sales.view_digital_sales')
@never_cache
@require_http_methods(['GET', 'POST'])
def order_detail(request, pk):
    order = get_object_or_404(DigitalOrder.objects.select_related('sale', 'buyer', 'supplier', 'edited_by'), pk=pk)
    form = forms.DraftForm(request.POST if request.method == 'POST' else None,
                           initial={'revision': order.revision, 'buyer': 'retail' if order.is_retail else order.buyer_id, 'price': order.price})
    if request.method == 'POST' and form.is_valid():
        try:
            services.save_draft(actor=request.user, order_id=pk, revision=form.cleaned_data['revision'],
                buyer_id=form.cleaned_data['buyer'].pk if isinstance(form.cleaned_data['buyer'], Buyer) else None,
                is_retail=form.cleaned_data['buyer'] == 'retail', price=form.cleaned_data['price'])
            return redirect('digital_sales:order', pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
            order.refresh_from_db()
    return render(request, 'digital_sales/order.html', {'order': order, 'form': form,
        'balance_after_completion': (order.buyer.balance - order.price
            if order.price is not None and order.buyer_id
            and (not order.sale_id or not order.sale.is_completed and not order.sale.is_cancelled) else None),
        'sources': order.messages.defer('encrypted_payload').order_by('pk'),
        'audit': _page(request, order.audit.select_related('actor').order_by('-pk'), 'audit_page', 100),
        'movements': order.sale.digital_movements.all() if order.sale_id else [],
        'asset_key': uuid.uuid4(), 'review_items': '\n'.join(f"{row['name']} | {row['cost']} | {row.get('number', '')}" for row in order.items),
        'unassigned': SupplierMessage.objects.filter(supplier=order.supplier, order__isnull=True).order_by('-pk')[:30]})


@sensitive_post_parameters('secret')
@sensitive_variables()
@permission_required_all('digital_sales.view_digital_sales')
@require_POST
def order_action(request, pk):
    order = get_object_or_404(DigitalOrder, pk=pk)
    action = request.POST.get('action')
    try:
        if order.processing_stopped and action != 'cancel':
            raise ValidationError('Заказ отменён и исключён из обработки.')
        if action == 'confirm':
            services.confirm_order(actor=request.user, order_id=pk, revision=request.POST.get('revision'))
        elif action == 'complete' and order.sale_id:
            services.complete_sale(actor=request.user, sale_id=order.sale_id)
        elif action == 'cancel' and order.sale_id:
            from sales.services import cancel_sale
            cancel_sale(actor=request.user, sale_id=order.sale_id, comment=request.POST.get('reason'))
        elif action == 'resolve':
            resolve_order(actor=request.user, order_id=pk, revision=request.POST.get('revision'), reason=request.POST.get('reason'))
        elif action == 'link':
            link_orders(actor=request.user, source_id=pk, target_id=request.POST.get('target'),
                        revision=request.POST.get('revision'), reason=request.POST.get('reason'))
        elif action == 'correct':
            items = forms.ItemsField().clean(request.POST.get('items'))
            correct_checklist(actor=request.user, order_id=pk, revision=request.POST.get('revision'), items=items,
                              reason=request.POST.get('reason'), goods_confirmed=request.POST.get('goods_confirmed') == 'yes')
        elif action == 'attach':
            attach_message(actor=request.user, order_id=pk, message_id=request.POST.get('message'),
                           revision=request.POST.get('revision'), reason=request.POST.get('reason'))
        elif action == 'retry_file':
            services.require(request.user, 'digital_sales.create_digital_sales')
            with transaction.atomic():
                source = get_object_or_404(SupplierMessage.objects.select_for_update(), pk=services.record_id(request.POST.get('message')), order=order)
                if source.attachment_state == 'error':
                    source.attachment_state = 'pending'
                    source.save(update_fields=['attachment_state'])
                    AuditEvent.objects.create(order=order, message=source, actor=request.user, kind='attachment_retry')
        elif action == 'asset':
            services.require(request.user, 'digital_sales.view_digital_secrets', 'digital_sales.create_digital_sales')
            with transaction.atomic():
                order = DigitalOrder.objects.select_for_update().get(pk=pk)
                services._version(order, request.POST.get('revision'))
                secret = str(request.POST.get('secret') or '')
                if not secret:
                    raise ValidationError('Введите данные товара.')
                store_manual_goods(order, secret, request.user, message_key=request.POST.get('asset_key'))
                order.revision += 1
                order.save(update_fields=['revision', 'updated_at'])
        else:
            raise ValidationError('Недопустимое действие.')
    except (ValidationError, ImproperlyConfigured) as exc:
        messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
    return redirect('digital_sales:order', pk=pk)


@sensitive_variables()
@permission_required_all('digital_sales.view_digital_sales', 'digital_sales.view_digital_secrets')
@never_cache
@require_POST
def reveal(request, pk):
    services.require(request.user, 'digital_sales.view_digital_secrets', 'digital_sales.view_digital_sales')
    source = get_object_or_404(SupplierMessage, pk=pk)
    payload = decrypt(source.encrypted_payload)
    AuditEvent.objects.create(order=source.order, message=source, actor=request.user, kind='secret_viewed')
    response = render(request, 'digital_sales/reveal.html', {'source': source, 'payload': payload})
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, noarchive'
    return response


@sensitive_variables()
@permission_required_all('digital_sales.view_digital_sales', 'digital_sales.view_digital_secrets')
@never_cache
@require_POST
def download(request, pk, index):
    services.require(request.user, 'digital_sales.view_digital_secrets', 'digital_sales.view_digital_sales')
    source = get_object_or_404(SupplierMessage, pk=pk)
    files = decrypt(source.encrypted_payload).get('attachments', [])
    if index >= len(files):
        raise Http404
    file = files[index]
    response = HttpResponse(base64.b64decode(file['data'], validate=True), content_type='application/octet-stream')
    response['Content-Disposition'] = content_disposition_header(True, str(file['name']).replace('\\', '/').rsplit('/', 1)[-1])
    response['X-Content-Type-Options'] = 'nosniff'
    response['Referrer-Policy'] = 'no-referrer'
    AuditEvent.objects.create(order=source.order, message=source, actor=request.user, kind='secret_downloaded')
    return response


@permission_required_all('digital_sales.configure_digital_bot')
@never_cache
@require_http_methods(['GET', 'POST'])
def configuration(request):
    bot = DigitalBot.objects.filter(pk=1).first() or DigitalBot()
    chosen = Supplier.objects.filter(pk=request.GET.get('supplier')).first() if request.GET.get('supplier', '').isdecimal() else None
    form = forms.BotForm(request.POST if request.POST.get('action') == 'bot' else None, instance=bot)
    supplier_form = forms.SupplierForm(request.POST if request.POST.get('action') == 'supplier' else None,
        instance=chosen, initial={'chat_ids': ','.join(map(str, chosen.chat_ids)), 'sender_ids': ','.join(map(str, chosen.sender_ids))} if chosen else None)
    diagnosis = None
    if request.method == 'POST':
        services.require(request.user, 'digital_sales.configure_digital_bot')
        try:
            if request.POST.get('action') == 'retry':
                services.record_id(request.POST.get('notification'))
            if request.POST.get('action') == 'resolve_balance':
                services.record_id(request.POST.get('observation'))
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('digital_sales:configuration')
        if request.POST.get('action') == 'bot' and form.is_valid():
            if bot.enabled and not Supplier.objects.exists():
                form.add_error(None, 'Сначала задайте разрешённый чат и отправителей.')
            else:
                form.save()
                return redirect('digital_sales:configuration')
        elif request.POST.get('action') == 'supplier' and supplier_form.is_valid():
            supplier_form.save()
            return redirect('digital_sales:configuration')
        elif request.POST.get('action') == 'diagnose':
            from .configuration import read_token
            from .worker import SupplierClient
            from telegram_bots.client import TelegramError
            try:
                client = SupplierClient(read_token())
                try:
                    me = client.call('getMe')
                    webhook = client.call('getWebhookInfo')
                    diagnosis = {'username': me.get('username'), 'privacy_disabled': me.get('can_read_all_group_messages', False),
                                 'webhook_present': bool(webhook.get('url')), 'chats': []}
                    for supplier in Supplier.objects.all():
                        for chat_id in supplier.chat_ids:
                            member = client.call('getChatMember', {'chat_id': chat_id, 'user_id': me['id']})
                            diagnosis['chats'].append({'chat': chat_id, 'status': member.get('status')})
                finally:
                    client.close()
            except (TelegramError, ValidationError) as exc:
                messages.error(request, 'Проверка Telegram не выполнена: ' + getattr(exc, 'category', 'configuration'))
        elif request.POST.get('action') == 'chat_retry':
            from .chat_balances import retry_publication
            from .models import BalanceChatPublication
            try:
                retry_publication(actor=request.user, publication_id=request.POST.get('publication'),
                    checked=request.POST.get('checked') == 'yes', message_id=request.POST.get('message_id'))
                messages.success(request, 'Обновление баланса поставлено в очередь.')
            except (ValidationError, BalanceChatPublication.DoesNotExist) as exc:
                messages.error(request, '; '.join(getattr(exc, 'messages', ['Публикация не найдена.'])))
        elif request.POST.get('action') == 'chat_command_retry':
            from .models import BalanceChatCommand
            services.require(request.user, 'digital_sales.manage_digital_buyers')
            try:
                with transaction.atomic():
                    command = get_object_or_404(BalanceChatCommand.objects.select_for_update(), pk=services.record_id(request.POST.get('command')))
                    if command.state == 'error':
                        command.state, command.error_category = 'queued', ''
                        command.save(update_fields=['state', 'error_category'])
                        AuditEvent.objects.create(actor=request.user, kind='chat_binding_retry', detail=f'command={command.pk}')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
        elif request.POST.get('action') == 'retry':
            with transaction.atomic():
                notification = get_object_or_404(Notification.objects.select_for_update(), pk=services.record_id(request.POST.get('notification')))
                if notification.state in ('error', 'uncertain'):
                    notification.state, notification.next_attempt_at = 'queued', None
                    notification.save(update_fields=['state', 'next_attempt_at'])
                    AuditEvent.objects.create(order=notification.order, actor=request.user, kind='notification_retry')
        elif request.POST.get('action') == 'resolve_balance':
            services.require(request.user, 'digital_sales.view_digital_reconciliation', 'digital_sales.adjust_digital_balances')
            observation = get_object_or_404(BalanceObservation, pk=services.record_id(request.POST.get('observation')))
            reason = str(request.POST.get('reason') or '').strip()
            if reason:
                observation.resolved_at, observation.resolution = timezone.now(), reason[:500]
                observation.save(update_fields=['resolved_at', 'resolution'])
                AuditEvent.objects.create(message=observation.message, actor=request.user, kind='balance_reviewed', detail=reason[:500])
    from .configuration import expected_status
    from .models import BuyerBalanceChat, BalanceChatPublication, BalanceChatCommand
    return render(request, 'digital_sales/configuration.html', {'form': form, 'supplier_form': supplier_form,
        'buyer_chats': BuyerBalanceChat.objects.select_related('buyer').order_by('title'),
        'chat_buyers': Buyer.objects.all(),
        'chat_errors': BalanceChatPublication.objects.select_related('chat', 'buyer').filter(state__in=['error', 'uncertain']).order_by('pk')[:30],
        'chat_commands': BalanceChatCommand.objects.select_related('chat').filter(state='error').order_by('-pk')[:30],
        'bot': bot, 'suppliers': Supplier.objects.all(), 'diagnosis': diagnosis, 'status': expected_status()})
