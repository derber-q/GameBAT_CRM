"""Session/CSRF расширения и штатная форма создания продажи."""
import json
import uuid
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, OperationalError
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from core.decorators import permission_required_any
from core.external_policy import require_live_operation
from .models import AvitoBrowserOrder
from . import avito_orders as service
from . import avito_sale_controls as controls


@never_cache
@permission_required_any('sales.create_sale')
@require_http_methods(['GET', 'POST'])
def bridge(request):
    try:
        require_live_operation('avito_browser_orders')
        if request.method == 'GET':
            return render(request, 'sales/avito_bridge.html', {'csrf':get_token(request)})
        if request.content_type != 'application/json' or len(request.body) > 3*1024*1024:
            raise ValidationError('Некорректный запрос расширения.')
        data = json.loads(request.body)
        action = data.get('action')
        if action == 'lookup':
            keys = data.get('ids')
            if not isinstance(keys, list) or len(keys) > 100:
                raise ValidationError('Некорректный список заказов.')
            keys = [service.order_id(k) for k in keys]
            rows = AvitoBrowserOrder.objects.select_related('sale').filter(external_id__in=keys)
            return JsonResponse({'ok':True, 'orders':{r.external_id:controls.summary(r, request.user) for r in rows},
                                 'status_css':controls.status_styles()})
        if action == 'sale_status':
            return JsonResponse({'ok':True, 'order':controls.change_status(data, request.user)})
        if action == 'cancel_sale':
            return JsonResponse({'ok':True, 'order':controls.cancel(data, request.user)})
        if action == 'draft':
            order = service.prepare_order(data['order'], request.user)
            url = reverse('sales:detail', args=[order.sale_id]) if order.sale_id else reverse('sales:avito_create', args=[order.pk])
            return JsonResponse({'ok':True, 'url':url})
        if action == 'print':
            from .avito_shipping import request_label
            job = request_label(actor=request.user, data=data)
            return JsonResponse({'ok':True, 'job_id':str(job.request_id), 'state':job.state})
        if action == 'print_status':
            from .models import AvitoShippingPrintJob
            job = get_object_or_404(AvitoShippingPrintJob, request_id=uuid.UUID(data['job_id']))
            return JsonResponse({'ok':True, 'state':job.state, 'message':job.last_error})
        raise ValidationError('Неизвестное действие расширения.')
    except (ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({'ok':False, 'message':'Некорректные данные расширения.'}, status=400)
    except PermissionDenied as error:
        return JsonResponse({'ok':False, 'message':str(error)}, status=403)
    except AvitoBrowserOrder.DoesNotExist:
        return JsonResponse({'ok':False, 'message':'Заказ не связан с CRM.'}, status=404)
    except ValidationError as error:
        status = {'test_environment_blocked':403, 'stale_sale':409}.get(getattr(error,'code',None),400)
        return JsonResponse({'ok':False, 'message':' '.join(error.messages)}, status=status)
    except OperationalError:
        return JsonResponse({'ok':False, 'message':'База занята. Повторите запрос.'}, status=409)


@permission_required_any('sales.create_sale')
def create(request, pk):
    require_live_operation('avito_browser_order_create')
    from .forms import SaleCreateForm
    from .models import Sale
    from .services import create_sale
    from .views import _parse_lines, _posted_initial_items, _consignment_options, _sale_destination
    order = get_object_or_404(AvitoBrowserOrder.objects.select_related('sale'), pk=pk)
    if order.sale_id:
        return _sale_destination(request, order.sale)
    initial = dict(sale_type=Sale.SaleType.AVITO, price_type=Sale.PriceType.RETAIL,
                   payment_method=Sale.PaymentMethod.BANK_TRANSFER_POSTPAY,
                   note=f'Avito #{order.external_id}. {order.carrier}\n'+ '\n'.join(order.titles))
    form = SaleCreateForm(request.POST or None, initial=initial)
    for field in ('sale_type', 'price_type'):
        form.fields[field].disabled = True
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                order = AvitoBrowserOrder.objects.select_for_update().select_related('sale').get(pk=pk)
                if not order.sale_id:
                    order.sale = create_sale(actor=request.user, warehouse_id=form.cleaned_data['warehouse'].pk,
                        sale_type=Sale.SaleType.AVITO, price_type=Sale.PriceType.RETAIL,
                        payment_method=form.cleaned_data['payment_method'], note=form.cleaned_data['note'],
                        cash_received_amount=form.cleaned_data['cash_received_amount'],
                        lines=_parse_lines(request.POST), creation_key=order.creation_key)
                    order.save(update_fields=['sale'])
            return _sale_destination(request, order.sale)
        except ValidationError as error:
            form.add_error(None, error)
        except OperationalError:
            form.add_error(None, 'База занята. Проверьте созданные продажи перед повтором.')
    return render(request, 'sales/create.html', {
        'form':form, 'creation_key':str(order.creation_key), 'avito_order':order,
        'initial_items':_posted_initial_items(request.POST) if request.method == 'POST' else service.initial_lines(order),
        'consignment_options':_consignment_options(), 'can_view_sales':request.user.has_perm('sales.view_sales'),
    })
