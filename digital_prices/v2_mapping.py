"""Консервативное сопоставление: старые PK и наценки сохраняются, ID не угадываются."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from .classification import region_code, code_characteristics


def normalized(value):
    return re.sub(r'[^\w]+', '', unicodedata.normalize('NFKC', str(value)).casefold())


def signature(row):
    kind = getattr(row, 'kind', getattr(row, 'source_type', ''))
    if kind != 'code':
        return None  # Исторические не-коды связываются только по неизменному v2 ID.
    attrs = row.attributes or {}
    name = getattr(row, 'name', getattr(row, 'source_name', ''))
    _, inferred = code_characteristics(name, attrs.get('code_category') or row.platform)
    denomination = attrs.get('denomination') or inferred.get('denomination', '')
    # Одинаковые числа с разными валютами/вариантами не объединяются.
    pieces = re.findall(r'\d+(?:[.,]\d+)?|[A-Za-zА-Яа-я]+', denomination)
    canonical = []
    for piece in pieces:
        try:
            canonical.append(format(Decimal(piece.replace(',', '.')).normalize(), 'f'))
        except InvalidOperation:
            canonical.append(normalized(piece))
    if not canonical:
        return None
    return (kind, normalized(attrs.get('family') or inferred.get('family') or row.platform),
            region_code(row.region), tuple(canonical), normalized(attrs.get('plan', '')), row.currency.upper())


def plan(offers, products):
    legacy, incoming = defaultdict(list), defaultdict(list)
    for row in products:
        if row.external_id.startswith('v1_code_') and not row.superseded_by_id and signature(row):
            legacy[signature(row)].append(row)
    for offer in offers:
        if signature(offer):
            incoming[signature(offer)].append(offer)
    by_id = {row.external_id: row for row in products}
    matched, ambiguous, missing = {}, {}, []
    for key, rows in legacy.items():
        candidates = incoming.get(key, [])
        if len(rows) == len(candidates) == 1 and candidates[0].identity not in by_id:
            matched[candidates[0].identity] = rows[0]
        elif candidates:
            for offer in candidates:
                ambiguous[offer.identity] = [row.pk for row in rows]
        else:
            missing.extend(row.pk for row in rows)
    return matched, ambiguous, missing


def report(offers, products):
    from .models import BuyerMarkup
    matched, ambiguous, missing = plan(offers, products)
    ids = [row.pk for row in products]
    return {'matched': [{'old_pk': row.pk, 'old_id': row.external_id, 'new_id': key} for key, row in matched.items()],
        'ambiguous': ambiguous, 'missing': missing,
        'new': [o.identity for o in offers if o.identity not in matched and not any(p.external_id == o.identity for p in products)],
        'general_markups': sum(p.markup is not None for p in products),
        'buyer_markups': BuyerMarkup.objects.filter(product_id__in=ids).count()}
