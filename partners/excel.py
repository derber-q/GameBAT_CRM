"""Подписанные сведения о заказчике внутри прежнего технического листа прайса."""
from django.core import signing
from django.core.exceptions import ValidationError
from .customers import resolve_customer

SALT = 'resource.wholesale-customer.v1'


def customer_metadata(*, warehouse_id, partner_id=None, partner_name=''):
    partner, name = resolve_customer(partner_id=partner_id, partner_name=partner_name)
    payload = {'warehouse_id': warehouse_id, 'partner_id': partner.pk if partner else None, 'name': name, 'version': 1}
    return {'customer_required': '1', 'customer_token': signing.dumps(payload, salt=SALT)}, name


def read_customer_metadata(values):
    if 'customer_token' not in values and 'customer_required' not in values:
        return None
    try:
        payload = signing.loads(values.get('customer_token', ''), salt=SALT)
        if (not isinstance(payload, dict) or payload.get('version') != 1
                or str(payload['warehouse_id']) != values.get('warehouse_id') or not isinstance(payload['name'], str)):
            raise ValueError()
        partner, name = resolve_customer(partner_id=payload['partner_id'],
            partner_name='' if payload['partner_id'] else payload['name'])
        if partner is None and not name:
            return None
        return {'partner_id': partner.pk if partner else None, 'partner_name': '' if partner else name}
    except (signing.BadSignature, KeyError, ValueError, TypeError, ValidationError) as exc:
        raise ValidationError('Сведения о заказчике в прайсе повреждены или недействительны. Сформируйте новый прайс.') from exc
