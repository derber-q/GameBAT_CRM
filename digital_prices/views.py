"""Серверные permissions, DTO строк и защищённые PNG вместо публичных media URL."""
from datetime import timedelta
from io import BytesIO
import zipfile
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST, require_http_methods
from core.decorators import permission_required_all, permission_required_any
from .models import Product, Integration, SyncJob, PriceBundle, PricePage, CatalogState, ManualPriceEntry, BuyerPriceDispatch
from .forms import ConfigurationForm, LayoutForm, ManualPriceForm, ManualPriceFormSet
from .services import edit_product, selling_price, enqueue_sync, save_configuration
from .public import safe_text
from .bundles import generate_bundle
from .catalog import catalog_slides, product_data, manual_data
from .buyer_pricing import selected_buyer, edit_buyer_markup

ERRORS = {'authentication': 'Проверьте ключ и доступ к каталогу', 'network': 'Нет соединения с поставщиком',
    'network_timeout': 'Поставщик не успел ответить. Сохранены прежние цены; обновление повторяется с увеличенным ожиданием.',
    'codes_authentication': 'Нет доступа к каталогу кодов поставщика',
    'invalid_codes': 'Каталог кодов содержит неподдерживаемые данные',
    'empty_codes_catalog': 'Получен пустой каталог кодов, прежний снимок сохранён',
    'rate_limited': 'Поставщик ограничил частоту запросов', 'upstream': 'Сервис поставщика временно недоступен',
    'empty_catalog': 'Получен пустой каталог, прежние данные сохранены',
    'configuration_changed': 'Настройки изменились во время обновления'}
SHEET_ERRORS = {'sheet_access':'Нет доступа к таблице. Предоставьте сервисному аккаунту CRM право чтения.',
    'sheet_credentials':'Не настроен сервисный аккаунт Google Sheets.',
    'sheet_network':'Не удалось соединиться с Google Sheets.', 'sheet_rate_limited':'Google временно ограничил запросы.',
    'sheet_unavailable':'Google Sheets временно недоступен.', 'sheet_structure':'Структура листа «Прайс» изменилась.',
    'sheet_mapping':'Не все ручные позиции удалось однозначно сопоставить с таблицей.',
    'sheet_prices_missing':'В таблице есть нулевые или пустые цены. Для этих строк сохранена прежняя себестоимость.',
    'sheet_local_changes':'Часть строк изменена сотрудником во время обновления и пропущена.',
    'sheet_price_format':'Цена в таблице имеет неподдерживаемый формат.',
    'sheet_response':'Ответ таблицы требует проверки.', 'sheet_empty':'В таблице нет тарифов.',
    'sheet_internal':'Не удалось прочитать таблицу тарифов.'}


def row_data(row, user):
    return product_data(row, user)


@never_cache
@permission_required_any('digital_prices.view_catalog', 'digital_prices.download_prices')
def catalog(request):
    if not request.user.has_perm('digital_prices.view_catalog'):
        return render(request, 'digital_prices/download.html')
    try:
        buyer = selected_buyer(request.GET.get('buyer'))
    except ValidationError as exc:
        return HttpResponse('; '.join(exc.messages), status=400)
    from digital_sales.models import Buyer
    content = catalog_slides(user=request.user, params=request.GET, buyer=buyer)
    config = Integration.objects.filter(pk=1).values('enabled','last_success_at','next_at','error_category',
        'manual_sheet_enabled','manual_sheet_url','manual_sheet_last_success_at','manual_sheet_error_category').first()
    if config and config['error_category']:
        config['error_category'] = ERRORS.get(config['error_category'], 'Ответ поставщика требует проверки администратором')
    if config and config['manual_sheet_error_category']:
        config['manual_sheet_error_category']=SHEET_ERRORS.get(config['manual_sheet_error_category'],'Таблица тарифов требует проверки.')
    jobs = []
    for job in SyncJob.objects.order_by('-created_at')[:6]:
        jobs.append({'created_at': job.created_at, 'source': 'Ежедневное' if job.source == 'daily' else 'Ручное',
            'state': {'pending': 'В очереди', 'running': 'Обновляется', 'done': 'Завершено', 'error': 'Ошибка'}.get(job.state, job.state),
            'item_count': job.item_count, 'summary': job.summary, 'last_attempt_at': job.last_attempt_at,
            'active': job.active, 'error_category': ERRORS.get(job.error_category, 'Требуется проверка') if job.error_category else ''})
    return render(request, 'digital_prices/catalog.html', {**content,
        'price_dispatches': BuyerPriceDispatch.objects.select_related('buyer', 'sync_job').annotate(
            pinned_pages=Count('deliveries', filter=Q(deliveries__state='pinned'))).order_by('-pk')[:8],
        'selected_buyer': buyer, 'buyers': Buyer.objects.order_by('name', 'pk'),
        'availability_choices': Product.Availability.choices, 'config': config,
        'jobs': jobs, 'catalog_revision': CatalogState.objects.get(pk=1).revision,
        'manual_url': reverse('pricing:digital_prices:manual') if request.user.has_perm('digital_prices.edit_manual_prices') else ''})


@never_cache
@permission_required_all('digital_prices.edit_manual_prices')
@require_http_methods(['GET', 'POST'])
def manual(request):
    from .manual import save_rows, FIELDS
    adding = request.method == 'POST' and request.POST.get('action') == 'add'
    queryset = ManualPriceEntry.objects.filter(source_archived=False)
    formset = ManualPriceFormSet(request.POST if request.method == 'POST' and not adding else None,
                                queryset=queryset)
    new_form = ManualPriceForm(request.POST if adding else None, prefix='new')
    if request.method == 'POST' and (new_form.is_valid() if adding else formset.is_valid()):
        try:
            if adding:
                changes = [{field: new_form.cleaned_data[field] for field in FIELDS}]
            else:
                changes = [{**{field: form.cleaned_data[field] for field in FIELDS},
                            'pk': form.instance.pk, 'revision': form.cleaned_data['revision']}
                           for form in formset.forms if form.has_changed()]
            save_rows(actor=request.user, changes=changes)
            messages.success(request, 'Ручные тарифы сохранены. API их не изменяет.')
            return redirect('pricing:digital_prices:manual')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return render(request, 'digital_prices/manual.html', {'formset': formset, 'new_form': new_form})


@never_cache
@permission_required_all('digital_prices.view_catalog')
def status(request):
    state = CatalogState.objects.get(pk=1)
    latest = SyncJob.objects.order_by('-created_at').first()
    return JsonResponse({'revision': state.revision, 'active': bool(latest and latest.active),
        'state': latest.state if latest else 'idle', 'summary': latest.summary if latest else {},
        'error': ERRORS.get(latest.error_category, 'Обновление требует проверки') if latest and latest.error_category else ''})


@require_POST
@never_cache
@permission_required_all('digital_prices.edit_markup')
def markup(request, pk):
    try:
        buyer = selected_buyer(request.POST.get('buyer'))
        values = {key: request.POST[key] for key in ('markup', 'manual_cost') if key in request.POST}
        row = (edit_buyer_markup(actor=request.user, buyer_id=buyer.pk, product_id=pk,
                    revision=request.POST.get('revision'), values=values) if buyer else
               edit_product(actor=request.user, product_id=pk, revision=request.POST.get('revision'), values=values))
        data = row_data(row, request.user)
        data['updated'] = data['updated'].isoformat() if data['updated'] else None
        return JsonResponse(data)
    except ValidationError as exc:
        return JsonResponse({'error': '; '.join(exc.messages)}, status=409 if getattr(exc, 'code', None) == 'conflict' else 400)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Товар не найден.'}, status=404)


@require_POST
@never_cache
@permission_required_any('digital_prices.edit_markup', 'digital_prices.edit_cost')
def manual_amounts(request, pk):
    from .manual import edit_amounts
    try:
        buyer = selected_buyer(request.POST.get('buyer'))
        values = {key: request.POST[key] for key in ('manual_cost', 'markup', 'cost_percent', 'markup_percent', 'cost_coefficient', 'markup_coefficient', 'pricing_mode', 'value') if key in request.POST}
        row = (edit_buyer_markup(actor=request.user, buyer_id=buyer.pk, entry_id=pk,
                    revision=request.POST.get('revision'), values=values) if buyer else
               edit_amounts(actor=request.user, entry_id=pk, revision=request.POST.get('revision'), values=values))
        return JsonResponse(manual_data(row, request.user))
    except ValidationError as exc:
        return JsonResponse({'error': '; '.join(exc.messages)}, status=409 if getattr(exc, 'code', None) == 'conflict' else 400)
    except ManualPriceEntry.DoesNotExist:
        return JsonResponse({'error': 'Тариф не найден.'}, status=404)


@require_POST
@permission_required_all('digital_prices.sync_catalog')
def sync(request):
    try:
        buyer = selected_buyer(request.POST.get('buyer'))
        enqueue_sync(actor=request.user)
        messages.success(request, 'Обновление поставлено в очередь. Последний подтверждённый каталог сохранён.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('pricing:digital_prices:catalog')
    return redirect(reverse('pricing:digital_prices:catalog') + (f'?buyer={buyer.pk}' if buyer else ''))


@never_cache
@permission_required_all('digital_prices.edit_layout')
@require_http_methods(['GET', 'POST'])
def layout(request, pk):
    row = get_object_or_404(Product, pk=pk)
    form = LayoutForm(request.POST or None, instance=row, initial={'revision': row.revision})
    if request.method == 'POST' and form.is_valid():
        try:
            edit_product(actor=request.user, product_id=pk, revision=form.cleaned_data['revision'],
                values={key: form.cleaned_data[key] for key in form.Meta.fields})
            return redirect('pricing:digital_prices:catalog')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'digital_prices/form.html', {'form': form, 'title': 'Оформление цифрового предложения'})


@never_cache
@sensitive_post_parameters('api_key')
@permission_required_all('digital_prices.configure_integration')
@require_http_methods(['GET', 'POST'])
def configuration(request):
    row = Integration.objects.filter(pk=1).first() or Integration()
    form = ConfigurationForm(request.POST or None, initial={key: getattr(row, key) for key in
        ('revision', 'enabled', 'daily_enabled', 'daily_at', 'timezone_name', 'manual_sheet_enabled', 'manual_sheet_url')})
    if request.method == 'POST' and form.is_valid():
        try:
            save_configuration(actor=request.user, **form.cleaned_data)
            return redirect('pricing:digital_prices:configuration')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'digital_prices/form.html', {'form': form, 'title': 'Настройка API цифрового каталога',
        'configured': bool(row.encrypted_key)})


@require_POST
@permission_required_all('digital_prices.download_prices')
def generate(request):
    try:
        buyer = selected_buyer(request.POST.get('buyer'))
        bundle = generate_bundle(actor=request.user, buyer=buyer)
    except (ValidationError, ValueError, OSError) as exc:
        text = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Не удалось сформировать полный комплект PNG.'
        return HttpResponse(text, status=400)
    return redirect('pricing:digital_prices:download' if request.POST.get('mode') == 'download' else
                    'pricing:digital_prices:preview', pk=bundle.pk)


@never_cache
@permission_required_all('digital_prices.download_prices')
def preview(request, pk):
    bundle = get_object_or_404(PriceBundle, pk=pk)
    return render(request, 'digital_prices/preview.html', {'bundle': bundle,
        'pages': bundle.pages.only('pk', 'index', 'filename')})


@never_cache
@permission_required_all('digital_prices.download_prices')
def png(request, pk):
    page = get_object_or_404(PricePage.objects.only('png'), pk=pk)
    response = HttpResponse(bytes(page.png), content_type='image/png')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@permission_required_all('digital_prices.download_prices')
def download(request, pk):
    bundle = get_object_or_404(PriceBundle, pk=pk)
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_STORED) as archive:
        for page in bundle.pages.all():
            archive.writestr(page.filename, bytes(page.png))
    response = HttpResponse(stream.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="GameBAT_digital_prices.zip"'
    response['Cache-Control'] = 'no-store'
    return response
