"""Полный каталог CRM: те же слайды и блоки, что у чистого PNG-рендерера."""
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from .models import Product, ManualPriceEntry
from .buyer_pricing import profile_rows
from .services import effective_rule
from .public import product_row, manual_row, safe_text, coefficient_text
from .layout import build_batches, group_key, order_group, order_row, card_info, slide_title, visible_subgroup


def markup_inputs(row, fields):
    """В полях — собственные значения, в расчёте — результат наследования."""
    data = {}
    for field in fields:
        own = getattr(row, 'buyer_markup_values', {}).get(field, getattr(row, field))
        general = getattr(row, 'general_markups', {}).get(field, getattr(row, field))
        format_value = coefficient_text if field == 'markup_coefficient' else lambda value: value
        data[field + '_input'] = format_value(own)
        data['general_' + field] = format_value(general)
    return data


def product_data(row, user, public=None):
    public = public or product_row(row)
    data = {'id': row.pk, 'name': public.name, 'label': public.label or public.name,
        'category': safe_text(row.category), 'availability': row.get_availability_display(),
        'review': row.requires_review, 'revision': getattr(row, 'profile_revision', row.revision), 'updated': row.confirmed_at,
        'price': public.price, 'variant': ' · '.join(filter(None, (public.family, public.region_label, public.subgroup))),
        'manual_source': False, 'kind': 'product', 'form_id': f'product-price-{row.pk}', 'rule': effective_rule(row),
        'edit_markup': user.has_perm('digital_prices.view_cost') and user.has_perm('digital_prices.edit_markup'),
        'edit_cost': False,
        'url': reverse('pricing:digital_prices:markup', args=[row.pk]),
        'subgroup': visible_subgroup(public)}
    data['inherited_markup'] = getattr(row, 'inherited_markup', False)
    if user.has_perm('digital_prices.view_cost'):
        cost, currency = row.purchase_cost, row.currency
        data.update(cost=cost if currency == 'RUB' else None, currency=currency,
                    markup=row.markup)
        data.update(markup_inputs(row, ('markup',)))
    data['editable'] = data['edit_markup'] or data['edit_cost']
    return data


def manual_data(entry, user, public=None):
    public = public or manual_row(entry)
    data = {'id': entry.pk, 'name': public.name, 'label': public.label, 'category': entry.get_kind_display(),
        'availability': 'Нет в наличии' if entry.sheet_issue == 'source_missing' else 'Тариф из Google Sheets' if entry.sheet_reference else 'Ручной тариф',
        'review': bool(entry.sheet_issue and entry.sheet_issue != 'source_missing'), 'revision': getattr(entry, 'profile_revision', entry.revision),
        'updated': max(filter(None,(entry.edited_at,entry.sheet_checked_at)),default=None),
        'sheet_issue': bool(entry.sheet_issue), 'sheet_reference': entry.sheet_reference,
        'price': public.price, 'kind': 'manual', 'manual_source': True, 'form_id': f'manual-price-{entry.pk}',
        'edit_markup': user.has_perm('digital_prices.view_cost') and user.has_perm('digital_prices.edit_markup'),
        'edit_cost': user.has_perm('digital_prices.view_cost') and user.has_perm('digital_prices.edit_cost'),
        'url': reverse('pricing:digital_prices:manual_amounts', args=[entry.pk]),
        'rule': Product.Rule.OTHER, 'subgroup': ''}
    if user.has_perm('digital_prices.view_cost'):
        data.update(cost=entry.manual_cost, manual_cost=entry.manual_cost, markup=entry.markup, currency='RUB',
            cost_percent=entry.cost_percent, markup_percent=entry.markup_percent, pricing_mode=entry.pricing_mode,
            cost_coefficient=coefficient_text(entry.cost_coefficient), markup_coefficient=coefficient_text(entry.markup_coefficient))
        data.update(markup_inputs(entry, ('markup','markup_percent','markup_coefficient')))
    data['editable'] = data['edit_markup'] or data['edit_cost']
    data['inherited_markup'] = getattr(entry, 'inherited_markup', False)
    if hasattr(entry, 'profile_revision'):
        data['edit_cost'] = False
        data['editable'] = data['edit_markup']
    data['edit_mode'] = data['edit_markup'] and data['edit_cost']
    return data


def matches(public, data, params, *, recent):
    if params.get('q') and params['q'][:200].casefold() not in ' '.join((public.name, public.label, data.get('variant', ''), data['category'])).casefold():
        return False
    if params.get('category') and data['category'] != params['category'][:120]:
        return False
    if params.get('cost_source') == 'manual' and not data['manual_source']:
        return False
    if params.get('availability') in Product.Availability.values and public.availability != params['availability']:
        return False
    if params.get('missing') == '1' and not data['missing_markup']:
        return False
    return not (params.get('recent') == '1' and not recent)


def heading_foreground(color):
    """Контрастный текст на неизменном цвете страны из PNG."""
    rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return '#102030' if sum(a*b for a, b in zip(linear, (.2126, .7152, .0722))) > .179 else '#ffffff'


def catalog_slides(*, user, params, buyer=None):
    products, manual = list(Product.objects.all()), list(ManualPriceEntry.objects.filter(source_archived=False))
    entries, data_by_row = [], {}
    cutoff = timezone.now() - timedelta(days=7)
    categories = set()
    for row in profile_rows(products, manual, buyer):
        is_product = isinstance(row, Product)
        public = product_row(row) if is_product else manual_row(row)
        data = product_data(row, user, public) if is_product else manual_data(row, user, public)
        data['missing_markup'] = (getattr(row, {'percent':'markup_percent','coefficient':'markup_coefficient'}.get(row.pricing_mode,'markup')) is None
                                  if not is_product else row.markup is None)
        categories.add(data['category'])
        entries.append(public)
        data_by_row[id(public)] = (data, row.first_seen_at >= cutoff if is_product else False)
    slides, shown = [], 0
    # Сначала группируется полный набор: фильтр не меняет номера и порядок слайдов.
    for number, (section, family, members) in enumerate(build_batches(entries), 1):
        groups = {}
        for public in members:
            groups.setdefault(group_key(public), []).append(public)
        blocks = []
        for key, rows in sorted(groups.items(), key=order_group):
            info = card_info(key, rows)
            data_rows = []
            previous = None
            for public in sorted(rows, key=order_row):
                data, recent = data_by_row[id(public)]
                if not matches(public, data, params, recent=recent):
                    continue
                data['show_subgroup'] = bool(data['subgroup'] and previous != data['subgroup'])
                previous = data['subgroup']
                data_rows.append(data)
            if data_rows:
                blocks.append({'title': info[2], 'subtitle': info[3], 'color': info[5],
                    'foreground': heading_foreground(info[5]), 'rows': data_rows})
                shown += len(data_rows)
        if blocks:
            slides.append({'number': number, 'title': slide_title(section, family), 'blocks': blocks,
                           'count': sum(len(block['rows']) for block in blocks)})
    return {'slides': slides, 'shown_count': shown, 'total_count': len(entries), 'categories': sorted(categories)}
