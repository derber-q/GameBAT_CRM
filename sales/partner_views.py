"""Предпросмотр подтверждения: суммы подписаны и заново сверяются при проведении."""
from decimal import Decimal
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from core.decorators import permission_required_any
from partners.models import Partner
from .models import Sale
from .partner_payments import quote, SALT, resolve_payment_partner


@never_cache
@require_POST
@permission_required_any('sales.create_sale', 'sales.mark_sale_paid')
def settlement_preview(request):
    sale_id = request.POST.get('sale_id')
    partner_id = request.POST.get('partner_id')
    if (sale_id and not sale_id.isdecimal()) or (not sale_id and (not partner_id or not partner_id.isdecimal())):
        return JsonResponse({'error': 'Выберите существующего партнёра или продажу.'}, status=400)
    if sale_id:
        if not request.user.has_perm('sales.mark_sale_paid'):
            return JsonResponse({'error': 'Нет права подтверждения оплаты.'}, status=403)
        sale = get_object_or_404(Sale, pk=sale_id, sale_type=Sale.SaleType.WHOLESALE,
            payment_status=Sale.PaymentStatus.UNPAID, cancelled_at__isnull=True)
        try:
            partner = resolve_payment_partner(sale, partner_id)
        except ValidationError as exc:
            return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
        total = sale.total_amount
        creation_key = None
    else:
        if not request.user.has_perm('sales.create_sale'):
            return JsonResponse({'error': 'Нет права создания продажи.'}, status=403)
        partner = get_object_or_404(Partner, pk=partner_id, is_archived=False)
        total, creation_key = request.POST.get('total'), request.POST.get('creation_key')
    if not partner:
        return JsonResponse({'error': 'У продажи нет партнёра из справочника.'}, status=400)
    try:
        values = quote(total=total, received=request.POST.get('received'), debt=partner.creditor.current_debt,
            partner_id=partner.pk, sale_id=int(sale_id) if sale_id else None, creation_key=creation_key)
    except ValidationError as exc:
        return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
    needed = any(Decimal(values[key]) > 0 for key in ('repayment', 'offset', 'charge'))
    if needed and not request.user.has_perm('creditors.change_debt'):
        return JsonResponse({'error': 'Для расчёта задолженности требуется право изменения долга.'}, status=403)
    if not needed:
        return JsonResponse({'required': False})
    return JsonResponse({'required': True, 'values': values, 'token': signing.dumps(values, salt=SALT)})
