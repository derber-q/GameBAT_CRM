"""Обратное заполнение только при явном подтверждении создания через веб-форму."""
import calendar
import hashlib
import re
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .audit import field_change, record_product_changes
from .models import CD, ProductChangeEvent, Tech
from .newness import newness_expiry


def previous_calendar_month(value):
    local = timezone.localtime(value)
    year, month = divmod(local.year * 12 + local.month - 2, 12)
    month += 1
    return local.replace(year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1]))


def web_creation_evidence(directory):
    """Строгая цепочка одного журнала: создание → POST 302 → GET нужной карточки 200."""
    found = defaultdict(list)
    if directory is None:
        return found
    root = Path(directory)
    if not root.is_dir():
        raise ValidationError('Каталог журналов веб-сервера не найден.')
    creation = re.compile(r'Товар создан: user_id=(\d+) type=(cd|tech) product_id=(\d+)\s*$')
    for path in sorted(root.glob('*.log')):
        raw = path.read_bytes()
        try:
            lines = raw.decode('utf-8').splitlines()
        except UnicodeDecodeError:
            lines = raw.decode('cp1251', errors='replace').splitlines()
        for index, line in enumerate(lines[:-1]):
            match = creation.search(line)
            if not match:
                continue
            actor_id, kind, pk = int(match[1]), match[2], int(match[3])
            request = lines[index + 1]
            if not re.search(r'"POST /crm/nomenclature/new/(?:\?[^ ]*)? HTTP/1\.[01]" 302 ', request):
                continue
            try:
                created = timezone.make_aware(datetime.strptime(line[:23], '%Y-%m-%d %H:%M:%S,%f'))
                requested = timezone.make_aware(datetime.strptime(request[:23], '%Y-%m-%d %H:%M:%S,%f'))
            except ValueError:
                continue
            if not 0 <= (requested - created).total_seconds() <= 2:
                continue
            detail_index = None
            for cursor in range(index + 2, min(index + 22, len(lines))):
                if creation.search(lines[cursor]):
                    break
                if f'"GET /crm/nomenclature/{kind}/{pk}/ HTTP/1.1" 200 ' in lines[cursor]:
                    try:
                        opened = timezone.make_aware(datetime.strptime(lines[cursor][:23], '%Y-%m-%d %H:%M:%S,%f'))
                    except ValueError:
                        break
                    if 0 <= (opened - requested).total_seconds() <= 5:
                        detail_index = cursor
                    break
            if detail_index is None:
                continue
            found[(kind, pk)].append({
                'actor_id': actor_id, 'logged_at': created.isoformat(), 'log': str(path),
                'creation_line': index + 1, 'post_line': index + 2, 'detail_line': detail_index + 1,
                'chain_sha256': hashlib.sha256('\n'.join((line, request, lines[detail_index])).encode('utf-8')).hexdigest(),
            })
    return found


def build_newness_backfill(*, user_id, as_of, web_evidence=None):
    if timezone.is_naive(as_of):
        raise ValidationError('Дата внедрения должна содержать часовой пояс.')
    since = previous_calendar_month(as_of)
    events = defaultdict(list)
    for event in ProductChangeEvent.objects.filter(field_changes__field_name='created').distinct().order_by('created_at', 'pk'):
        if event.product_id is not None:
            events[(event.product_kind, event.product_id)].append(event)
    rows = []
    web_evidence = web_evidence or {}
    for kind, model in (('cd', CD), ('tech', Tech)):
        for product in model.objects.order_by('pk'):
            candidates = events[(kind, product.pk)]
            event = candidates[0] if len(candidates) == 1 else None
            http_matches = [proof for proof in web_evidence.get((kind, product.pk), ())
                            if event and event.source == ProductChangeEvent.Source.NOMENCLATURE
                            and event.actor_id == proof['actor_id']
                            and abs((event.created_at - datetime.fromisoformat(proof['logged_at'])).total_seconds()) <= 1]
            http_proof = http_matches[0] if len(http_matches) == 1 else None
            created_at = product.created_at or (event.created_at if event else None)
            created_by = product.created_by_id or (event.actor_id if event else None)
            automatic = product.creation_source == model.CreationSource.AUTOMATIC or bool(
                event and (event.action_kind == 'product_automatic_create' or
                           (event.source == ProductChangeEvent.Source.CRM and event.actor_id is None)))
            web = bool(http_proof) or product.creation_source == model.CreationSource.WEB or bool(
                event and event.action_kind == 'product_web_create' and
                event.source == ProductChangeEvent.Source.NOMENCLATURE and event.actor_id is not None)
            status, reason = 'uncertain', 'В старом аудите веб-форма и скрипт от имени сотрудника не различались.'
            if product.is_archived:
                status, reason = 'archived', 'Карточка архивирована.'
            elif automatic and web:
                reason = 'Источники происхождения противоречат друг другу.'
            elif automatic:
                status, reason = 'automatic', 'Есть явный автоматический источник либо создание CRM без сотрудника.'
            elif not created_at:
                reason = 'Дата создания отсутствует; однозначное событие создания не найдено.'
            elif not since <= created_at <= as_of:
                status, reason = 'outside_period', 'Создание вне последнего календарного месяца.'
            elif not web:
                reason = 'Не подтверждено создание именно через HTTP-форму; created_by и источник «Номенклатура» недостаточны.'
            elif created_by != user_id:
                status, reason = 'other_user', 'Нет подтверждения создания указанным пользователем.'
            elif product.newness_backfill_checked_at or product.newness_months or product.newness_until:
                status, reason = 'configured', 'Статус уже настроен пользователем или перенос ранее выполнен.'
            else:
                status, reason = 'eligible', 'Явно подтверждённая веб-форма нужного пользователя в указанном периоде.'
            rows.append({
                'kind': kind, 'id': product.pk, 'name': product.name,
                'created_at': created_at.isoformat() if created_at else None,
                'stored_created_at': product.created_at.isoformat() if product.created_at else None,
                'date_source': 'product' if product.created_at else 'creation_audit' if event else None,
                'created_by': created_by, 'stored_created_by': product.created_by_id,
                'creation_source': product.creation_source,
                'creation_event_id': event.pk if event else None,
                'creation_event_count': len(candidates),
                'http_creation_proof': http_proof,
                'newness_months': product.newness_months,
                'newness_until': product.newness_until.isoformat() if product.newness_until else None,
                'checked_at': product.newness_backfill_checked_at.isoformat() if product.newness_backfill_checked_at else None,
                'status': status, 'reason': reason,
            })
    return {'as_of': timezone.localtime(as_of).isoformat(), 'since': since.isoformat(), 'user_id': user_id,
            'counts': dict(Counter(row['status'] for row in rows)), 'rows': rows}


@transaction.atomic
def apply_newness_backfill(plan):
    """Неподтверждённые карточки не изменяются, включая служебные отметки."""
    changed = []
    for row in plan['rows']:
        if row['status'] != 'eligible':
            continue
        model = CD if row['kind'] == 'cd' else Tech
        product = model.objects.select_for_update().get(pk=row['id'])
        if (product.newness_months != row['newness_months'] or product.newness_until or
                product.newness_backfill_checked_at or product.is_archived or
                (product.created_at.isoformat() if product.created_at else None) != row['stored_created_at'] or
                product.creation_source != row['creation_source'] or product.created_by_id != row['stored_created_by']):
            raise ValidationError(f'{product.name}: карточка изменилась после dry-run; повторите проверку.')
        created_at = datetime.fromisoformat(row['created_at'])
        product.created_at = created_at
        product.created_by_id = row['created_by']
        product.creation_source = model.CreationSource.WEB
        product.newness_months = 1
        product.newness_until = newness_expiry(created_at, 1)
        product.newness_backfill_checked_at = timezone.now()
        product.full_clean()
        product.save(update_fields=('created_at', 'created_by', 'creation_source', 'newness_months',
                                    'newness_until', 'newness_backfill_checked_at'))
        record_product_changes(
            actor=None, instance=product, source=ProductChangeEvent.Source.CRM,
            action_kind='newness_backfill', action_object_id=product.pk,
            action_label='Системный перенос статуса новинки',
            changes=[field_change(field_name='newness_months', field_label='Срок новинки, месяцев', old_value=0, new_value=1),
                     field_change(field_name='newness_until', field_label='Новинка до', old_value='', new_value=product.newness_until.isoformat()),
                     field_change(field_name='creation_source', field_label='Подтверждённое происхождение', old_value=row['creation_source'], new_value=product.creation_source),
                     field_change(field_name='created_at', field_label='Дата создания из аудита', old_value=row['stored_created_at'] or '', new_value=created_at.isoformat()),
                     field_change(field_name='creation_verification', field_label='Основание переноса', old_value='',
                                  new_value=f'Событие создания #{row["creation_event_id"]}; HTTP: {row["http_creation_proof"]}' if row['http_creation_proof'] else 'Явное происхождение «Веб-форма» и пользователь карточки.')],
        )
        changed.append({'kind': row['kind'], 'id': product.pk, 'newness_until': product.newness_until.isoformat()})
    return changed
