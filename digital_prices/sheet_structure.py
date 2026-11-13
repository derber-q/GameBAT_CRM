"""Согласованное принятие подтверждённой новой сетки СНГ без удаления старых строк."""
from .classification import region_code
from .models import AuditEvent
from .sheet_source import normalized_label

SNG_OLD = frozenset(('1-99', '100-349', '350-999', '1000-1999', '2000-2999', '3000-3999', '4000+'))
SNG_CURRENT = frozenset(('1-99', '100-349', '350-999', '1000-1999', '2000+'))


def reconcile_sng(rows, costs, revisions):
    """Вызывается под блокировкой CatalogState в транзакции применения каталога.

    Допускается только подтверждённый переход 7→5. Любые другие отличия
    сохраняют прежний снимок с ошибкой сопоставления, а не угадываются.
    """
    def key(row):
        return row.kind, region_code(row.region), normalized_label(row.label)
    active = [row for row in rows if not row.source_archived]
    sng = [row for row in active if key(row)[:2] == ('game_tariff', 'sng')]
    source = {label for kind, region, label in costs if (kind, region) == ('game_tariff', 'sng')}
    current = {normalized_label(row.label) for row in sng}
    if current != SNG_OLD or source != SNG_CURRENT:
        return active, ''
    if len(sng) != len(SNG_OLD):
        return active, 'sheet_mapping'
    changed = [row for row in sng if normalized_label(row.label) in ('2000-2999', '3000-3999', '4000+')]
    # Сначала проверяем весь план, чтобы ошибка не оставляла половину новой сетки.
    if revisions is not None and any(revisions.get(row.pk) != row.revision for row in changed):
        return active, 'sheet_local_changes'
    future_keys = set()
    for row in active:
        kind, region, label = key(row)
        if (kind, region) == ('game_tariff', 'sng'):
            if label in ('3000-3999', '4000+'):
                continue
            if label == '2000-2999':
                label = '2000+'
        future_keys.add((kind, region, label))
    if not future_keys.issubset(costs):
        return active, 'sheet_mapping'
    history = []
    for row in changed:
        old_label = row.label
        if normalized_label(row.label) == '2000-2999':
            row.label = '2000+'
        else:
            row.source_archived = True
        row.revision += 1
        row.full_clean()
        row.save(update_fields=['label', 'source_archived', 'revision'])
        if revisions is not None:
            revisions[row.pk] = row.revision
        history.append({'entry': row.pk, 'old_label': old_label, 'label': row.label, 'archived': row.source_archived})
    AuditEvent.objects.create(kind='sheet_structure', detail={'region': 'sng', 'rows': history})
    return [row for row in active if not row.source_archived], ''
