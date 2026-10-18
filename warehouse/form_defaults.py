from django import forms

from .models import Warehouse


def single_warehouse_id():
    """Возвращает склад по умолчанию, только если во всей базе он один."""
    ids = list(Warehouse.objects.values_list("pk", flat=True)[:2])
    return ids[0] if len(ids) == 1 else None


class SingleWarehouseInitialMixin:
    """Подставляет единственный склад в новые формы, сохраняя ввод и начальные значения."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            return
        fields = [
            (name, field) for name, field in self.fields.items()
            if isinstance(field, forms.ModelChoiceField)
            and not isinstance(field, forms.ModelMultipleChoiceField)
            and field.queryset.model is Warehouse
            and not field.disabled
            and self.initial.get(name, field.initial) in (None, "")
        ]
        if not fields:
            return
        warehouse_id = single_warehouse_id()
        if warehouse_id is None:
            return
        for name, field in fields:
            if field.queryset.filter(pk=warehouse_id).exists():
                self.initial[name] = warehouse_id
