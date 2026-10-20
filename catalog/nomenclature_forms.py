"""Явные формы карточек с серверной проверкой прав на каждое поле."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.forms import BaseFormSet, formset_factory
from django.urls import reverse
from partners.models import Supplier

from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.storage_locations import normalize_storage_location_list

from .models import BarcodeRegistry, CD, Tech
from .product_fields import (
    CD_CARD_FIELDS,
    CD_FIELD_PERMISSIONS,
    TECH_CARD_FIELDS,
    TECH_FIELD_PERMISSIONS,
)
from .removal import normalize_removal_selection


class BulkProductDeleteForm(forms.Form):
    selection = forms.JSONField(label="Выбранные товары")
    confirm = forms.ChoiceField(choices=(("yes", "Подтверждаю удаление"),))
    query = forms.CharField(required=False, max_length=4000)
    list_kind = forms.ChoiceField(
        required=False, choices=(("", "Все товары"), ("cd", "Диски"), ("tech", "Техника")),
    )

    def clean_selection(self):
        return normalize_removal_selection(self.cleaned_data["selection"])

    def clean(self):
        data = super().clean()
        list_kind = data.get("list_kind")
        if list_kind and any(
            not token.startswith(f"{list_kind}:") for token in data.get("selection", ())
        ):
            self.add_error("selection", "Выбраны товары из другого раздела номенклатуры.")
        return data


def product_version(instance):
    """Возвращает optimistic-lock token для карточки и её складских остатков."""
    values = {}
    field_names = CD_CARD_FIELDS if isinstance(instance, CD) else TECH_CARD_FIELDS
    for field_name in field_names:
        field = instance._meta.get_field(field_name)
        value = getattr(instance, field.attname if field.is_relation else field_name)
        if value is not None and hasattr(field, "decimal_places"):
            # После чтения из БД Decimal получает точность поля. Это не изменение карточки.
            value = format(Decimal(str(value)), f".{field.decimal_places}f")
        values[field_name] = value
    if instance.pk:
        values["barcodes"] = list(instance.barcodes.order_by("id").values_list("value", flat=True))
        values['excluded_suppliers'] = list(instance.supplier_exclusions.order_by('supplier_id').values_list('supplier_id', flat=True))
        stocks = list(
            instance.warehouse_stocks.order_by("warehouse_id").prefetch_related(
                "storage_assignments__location"
            )
        )
        values["warehouse_stocks"] = [
            (stock.warehouse_id, stock.quantity) for stock in stocks
        ]
        values["warehouse_storage_locations"] = [
            (
                stock.warehouse_id,
                [
                    assignment.location.canonical_value
                    for assignment in stock.storage_assignments.all()
                ],
            )
            for stock in stocks
        ]
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SupplierExclusionChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, supplier):
        return f'{supplier.safe_label} — Не участвует в подборе'


class ProductOptionsForm(forms.ModelForm):
    newness_months = forms.ChoiceField(
        label='Продолжительность', initial='1',
        choices=(('0', 'Не делать новинкой'), ('1', '1 месяц'), ('3', '3 месяца'),
                 ('5', '5 месяцев'), ('custom', 'Своё количество месяцев')),
        widget=forms.Select(attrs={'data-newness-duration': ''}),
    )
    newness_custom_months = forms.IntegerField(
        label='Своё количество месяцев', min_value=1, required=False,
        widget=forms.NumberInput(attrs={'data-newness-custom': '', 'min': '1', 'step': '1'}),
    )
    excluded_suppliers = SupplierExclusionChoiceField(
        label='Исключить поставщиков из подбора', queryset=Supplier.objects.none(),
        required=False, widget=forms.CheckboxSelectMultiple,
        help_text='Предложения сохраняются и принимаются из Excel, но не участвуют в новом подборе и назначении закупки.',
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.creation_date_event = None
        self.recovered_creation_date = False
        self.fields['excluded_suppliers'].queryset = Supplier.objects.all()
        if self.instance.pk:
            months = self.instance.newness_months
            self.initial['newness_months'] = str(months) if months in (0, 1, 3, 5) else 'custom'
            self.initial['newness_custom_months'] = months if months not in (0, 1, 3, 5) else None
            self.initial['excluded_suppliers'] = list(self.instance.supplier_exclusions.values_list('supplier_id', flat=True))
            allowed = user and (user.is_superuser or user.has_perm(f'catalog.change_{self.instance._meta.model_name}'))
            if not allowed or self.instance.is_archived:
                for name in ('newness_months', 'newness_custom_months', 'excluded_suppliers'):
                    self.fields[name].disabled = True
                    self.fields[name].required = False
        if self.instance.pk and self.instance.created_at is None:
            events = list(self.instance.change_events.filter(field_changes__field_name='created').distinct().order_by('pk')[:2])
            if len(events) == 1:
                self.creation_date_event = events[0]
                self.fields['newness_months'].help_text = 'При выборе срока дата создания будет восстановлена из единственного события создания в истории. Срок не начинается заново.'
            else:
                self.fields['newness_months'].help_text = 'Дата создания старой карточки не подтверждена. Назначение положительного срока будет отклонено.'

    def clean(self):
        data = super().clean()
        duration = data.get('newness_months')
        if duration == 'custom':
            months = data.get('newness_custom_months')
            if months is None:
                self.add_error('newness_custom_months', 'Укажите положительное целое количество месяцев.')
                data.pop('newness_months', None)
            else:
                data['newness_months'] = months
        elif duration is not None:
            data['newness_months'] = int(duration)
        if data.get('newness_months', 0) > 0 and self.instance.pk and self.instance.created_at is None and self.creation_date_event:
            # Это только восстановление даты для явного выбора пользователя,
            # а не автоматическое присвоение статуса или ручного происхождения.
            self.instance.created_at = self.creation_date_event.created_at
            self.recovered_creation_date = True
        return data


class ProductCardFormMixin(ProductOptionsForm):
    version = forms.CharField(widget=forms.HiddenInput)
    cost_confirmed = forms.BooleanField(required=False, widget=forms.HiddenInput)
    field_permissions = {}

    def __init__(self, *args, user, **kwargs):
        submitted = args[0] if args else kwargs.get('data')
        self.submitted_fields = set(submitted or ())
        instance = kwargs.get('instance')
        if submitted is not None and instance is not None and instance.pk:
            # Старые открытые формы не содержат новых опций. Их отсутствие
            # сохраняет настройки; новая форма отмечает явное снятие checkbox.
            compatible = submitted.copy()
            if 'newness_months' not in compatible:
                months = instance.newness_months
                compatible['newness_months'] = str(months) if months in (0, 1, 3, 5) else 'custom'
                if months not in (0, 1, 3, 5):
                    compatible['newness_custom_months'] = str(months)
            if 'excluded_suppliers' not in compatible and 'product_options_present' not in compatible:
                ids = list(instance.supplier_exclusions.values_list('supplier_id', flat=True))
                if hasattr(compatible, 'setlist'):
                    compatible.setlist('excluded_suppliers', [str(pk) for pk in ids])
                else:
                    compatible['excluded_suppliers'] = ids
            if args:
                args = (compatible, *args[1:])
            else:
                kwargs['data'] = compatible
        super().__init__(*args, user=user, **kwargs)
        self.user = user
        self.fields["weight_grams"].label = "Вес с упаковкой, г"
        self.allowed_fields = {
            field_name
            for field_name, permission in self.field_permissions.items()
            if user.is_superuser or user.has_perm(permission)
        }
        if user.is_superuser or user.has_perm(f'catalog.change_{self.instance._meta.model_name}'):
            self.allowed_fields.update({'excluded_suppliers', 'newness_custom_months'})
        self.forbidden_fields = []
        stock_model = CDWarehouseStock if isinstance(self.instance, CD) else TechWarehouseStock
        stock_permission = (
            "warehouse.change_cdwarehousestock"
            if isinstance(self.instance, CD)
            else "warehouse.change_techwarehousestock"
        )
        self.can_change_stock = not self.instance.is_archived and (
            user.is_superuser or user.has_perm(stock_permission)
        )
        stocks = list(
            stock_model.objects.filter(
                **{self.instance._meta.model_name: self.instance}
            ).prefetch_related("storage_assignments__location")
        ) if self.instance.pk else []
        stock_values = {stock.warehouse_id: stock.quantity for stock in stocks}
        storage_location_values = {
            stock.warehouse_id: ", ".join(
                assignment.location.canonical_value
                for assignment in stock.storage_assignments.all()
            )
            for stock in stocks
        }
        self.stock_fields = []
        self.storage_location_fields = []
        self.warehouse_field_pairs = []
        self.warehouses_by_id = {warehouse.pk: warehouse for warehouse in Warehouse.objects.all()}
        self.can_change_storage_location = not self.instance.is_archived and (
            user.is_superuser or user.has_perm("warehouse.change_storage_location")
        )
        for warehouse in self.warehouses_by_id.values():
            stock_field_name = f"stock_{warehouse.pk}"
            self.fields[stock_field_name] = forms.IntegerField(
                label=warehouse.name,
                min_value=0,
                initial=stock_values.get(warehouse.pk, 0),
                disabled=not self.can_change_stock,
                required=self.can_change_stock,
                widget=forms.NumberInput(attrs={"min": 0, "step": 1}),
            )
            if not self.can_change_stock:
                self.fields[stock_field_name].widget.attrs["aria-readonly"] = "true"
            else:
                self.allowed_fields.add(stock_field_name)
            self.stock_fields.append(stock_field_name)

            location_field_name = f"storage_location_{warehouse.pk}"
            self.fields[location_field_name] = forms.CharField(
                label=f"Место хранения: {warehouse.name}",
                initial=storage_location_values.get(warehouse.pk, ""),
                required=False,
                disabled=not self.can_change_storage_location,
                widget=forms.TextInput(attrs={
                    "placeholder": "",
                    "autocomplete": "off",
                    "data-storage-location-autocomplete": "true",
                    "data-autocomplete-url": reverse(
                        "warehouse:storage_location_autocomplete", args=(warehouse.pk,)
                    ),
                    "aria-label": f"Место хранения: {warehouse.name}",
                }),
            )
            if not self.can_change_storage_location:
                self.fields[location_field_name].widget.attrs["aria-readonly"] = "true"
            else:
                self.allowed_fields.add(location_field_name)
            self.storage_location_fields.append(location_field_name)
            self.warehouse_field_pairs.append((stock_field_name, location_field_name))
        self.fields["version"].initial = product_version(self.instance)
        self.fields["cost"].widget.attrs.update({"min": "0", "step": "0.01", "data-cost-input": "true"})
        for field_name in ("sku",):
            if not getattr(self.instance, field_name):
                # Старые импортированные карточки могут содержать пустой артикул.
                # Это не должно блокировать изменение другого разрешённого поля.
                self.fields[field_name].required = False
        for field_name in self.field_permissions:
            field = self.fields[field_name]
            if field_name not in self.allowed_fields or self.instance.is_archived:
                field.disabled = True
                field.required = False
                field.widget.attrs["aria-readonly"] = "true"
        if self.instance.is_archived:
            self.allowed_fields.clear()
        for field_name in ("description", "comment"):
            self.fields[field_name].widget.attrs.setdefault("rows", 4)
        self.can_edit = bool(self.allowed_fields)
        for name in ("avito_markup_from_wholesale", "yandex_markup_from_wholesale"):
            self.fields[name].help_text = "Минимальная разница с оптовой ценой, ₽. Пусто — не проверять наценку. Проверка цены ниже себестоимости остаётся."
        from pricing.warnings import MARKUP_FOR_PRICE, price_warning
        def money(name):
            try:
                value = Decimal(str(self[name].value()).replace(",", "."))
                return value if value.is_finite() else None
            except (InvalidOperation, TypeError, ValueError):
                return None
        for name in ("avito_price", "wholesale_price", "yandex_market_price"):
            attrs = self.fields[name].widget.attrs
            attrs["data-price-field"] = name
            reason = price_warning(
                price=money(name), wholesale=money("wholesale_price"), cost=self.instance.cost,
                markup=money(MARKUP_FOR_PRICE[name]) if name in MARKUP_FOR_PRICE else None,
            )
            attrs["title"] = reason
            if reason:
                attrs["class"] = (attrs.get("class", "") + " price-warning").strip()
        for name, markup_name in MARKUP_FOR_PRICE.items():
            self.fields[markup_name].widget.attrs["data-markup-for"] = name

    def clean(self):
        cleaned_data = super().clean()
        if not self.is_bound:
            return cleaned_data
        accepted_keys = self.allowed_fields | {"version", "cost_confirmed", "csrfmiddlewaretoken", 'product_options_present'}
        self.forbidden_fields = sorted(self.submitted_fields - accepted_keys)
        if self.forbidden_fields:
            labels = []
            for field_name in self.forbidden_fields:
                if field_name in self.fields:
                    labels.append(str(self.fields[field_name].label))
                else:
                    try:
                        labels.append(str(self.instance._meta.get_field(field_name).verbose_name))
                    except FieldDoesNotExist:
                        labels.append(field_name)
            raise ValidationError(
                "Нет права изменять поля: %(fields)s.",
                params={"fields": ", ".join(labels)},
                code="forbidden_fields",
            )
        for field_name in self.storage_location_fields:
            if field_name not in self.allowed_fields or field_name not in cleaned_data:
                continue
            try:
                cleaned_data[field_name] = normalize_storage_location_list(cleaned_data[field_name])
            except ValidationError as exc:
                self.add_error(field_name, exc)
        return cleaned_data


class CDCardForm(ProductCardFormMixin):
    field_permissions = CD_FIELD_PERMISSIONS

    class Meta:
        model = CD
        fields = CD_CARD_FIELDS


class TechCardForm(ProductCardFormMixin):
    field_permissions = TECH_FIELD_PERMISSIONS

    class Meta:
        model = Tech
        fields = TECH_CARD_FIELDS


class ProductCreateFormMixin(ProductOptionsForm):
    """Форма создаёт только карточку — без остатков, себестоимости и цен."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sku"].required = False
        self.fields["weight_grams"].label = "Вес с упаковкой, г"
        for field_name in ("description", "comment"):
            self.fields[field_name].widget.attrs.setdefault("rows", 4)


class CDCreateForm(ProductCreateFormMixin, forms.ModelForm):
    class Meta:
        model = CD
        fields = (
            "platform", "game_series", "name", "description", "sku", "cusa_ppsa_code",
            "weight_grams", "length_cm", "width_cm", "height_cm", "comment", "exclude_from_supplier_template",
            'newness_months',
        )


class TechCreateForm(ProductCreateFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["length_cm"].help_text = "Для геймпадов пустые размеры заполнятся значениями 21 × 20 × 11 см."

    class Meta:
        model = Tech
        fields = (
            "brand", "product_type", "name", "description", "sku",
            "weight_grams", "length_cm", "width_cm", "height_cm", "comment", "exclude_from_supplier_template",
            'newness_months',
        )


class ProductBarcodeForm(forms.Form):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    value = forms.CharField(
        label="Штрихкод", max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    DELETE = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def clean_value(self):
        value = str(self.cleaned_data.get("value") or "").strip()
        if not value:
            raise ValidationError("Укажите штрихкод.")
        return value


class BaseProductBarcodeFormSet(BaseFormSet):
    deletion_widget = forms.HiddenInput

    def __init__(self, *args, product=None, **kwargs):
        self.product = product
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        values = []
        owner_filter = {"cd": self.product} if isinstance(self.product, CD) else {"tech": self.product}
        deleting_ids = {
            form.cleaned_data.get("id") for form in self.forms
            if form.cleaned_data and form.cleaned_data.get("DELETE")
        }
        for form in self.forms:
            if not form.cleaned_data:
                continue
            barcode_id = form.cleaned_data.get("id")
            if barcode_id and (self.product is None or not BarcodeRegistry.objects.filter(
                pk=barcode_id, **owner_filter,
            ).exists()):
                raise ValidationError("Штрихкод не принадлежит этому товару.")
            if form.cleaned_data.get("DELETE"):
                continue
            value = form.cleaned_data.get("value")
            if not value:
                continue
            if value in seen:
                raise ValidationError(f"Штрихкод {value} указан несколько раз.")
            seen.add(value)
            values.append(value)
            occupied = BarcodeRegistry.objects.filter(value=value).first()
            if occupied and occupied.pk != barcode_id and occupied.pk not in deleting_ids:
                raise ValidationError("Этот штрихкод уже используется другим товаром или строкой.")


ProductBarcodeFormSet = formset_factory(
    ProductBarcodeForm,
    formset=BaseProductBarcodeFormSet,
    extra=1,
    can_delete=True,
)


def barcode_formset(*, data=None, product=None):
    initial = [
        {"id": item.pk, "value": item.value}
        for item in product.barcodes.order_by("id")
    ] if product and product.pk else []
    return ProductBarcodeFormSet(data=data, initial=initial, product=product, prefix="barcodes")
