import json

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from catalog.models import CD, Tech

from .models import AvitoProductPhoto, AvitoProductProfile


class CredentialForm(forms.Form):
    client_id = forms.CharField(
        label="Client ID", required=False, max_length=255,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )
    client_secret = forms.CharField(
        label="Client secret", required=False, max_length=255,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )


class AvitoProfileForm(forms.ModelForm):
    attributes = forms.JSONField(
        label="Поля Avito (JSON)", required=False,
        widget=forms.Textarea(attrs={"rows": 8, "spellcheck": "false", "class": "mono"}),
    )

    class Meta:
        model = AvitoProductProfile
        fields = (
            "sell_on_avito", "listing_title", "listing_description", "category_slug", "attributes",
        )
        widgets = {"listing_description": forms.Textarea(attrs={"rows": 5})}

    def clean_attributes(self):
        value = self.cleaned_data.get("attributes") or {}
        if not isinstance(value, dict):
            raise ValidationError("Укажите JSON-объект: пары «поле: значение».")
        if not self.instance.schema_snapshot and self.instance.pk:
            previous = AvitoProductProfile.objects.filter(pk=self.instance.pk).values_list("attributes", flat=True).first() or {}
            if value != previous:
                raise ValidationError(
                    "Нельзя изменять поля без официальной схемы Avito. Для аккаунта сейчас закрыт Autoload API."
                )
        return value


class AvitoPhotoForm(forms.ModelForm):
    class Meta:
        model = AvitoProductPhoto
        fields = ("image",)

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > 10 * 1024 * 1024:
            raise ValidationError("Размер фотографии не должен превышать 10 МБ.")
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if getattr(image, "content_type", "") not in allowed:
            raise ValidationError("Разрешены JPEG, PNG и WebP.")
        return image


class ProductTargetForm(forms.Form):
    product_ref = forms.ChoiceField(label="Товар CRM")

    def __init__(self, *args, query="", exclude_connected=True, **kwargs):
        super().__init__(*args, **kwargs)
        query = str(query or "").strip()
        cd_qs = CD.objects.active().select_related("platform")
        tech_qs = Tech.objects.active().select_related("brand", "product_type")
        if query:
            cd_qs = cd_qs.filter(
                Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcodes__value__icontains=query)
                | Q(cusa_ppsa_code__icontains=query)
            )
            tech_qs = tech_qs.filter(
                Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcodes__value__icontains=query)
            )
            cd_qs = cd_qs.distinct()
            tech_qs = tech_qs.distinct()
        if exclude_connected:
            cd_qs = cd_qs.filter(avito_profile__connection__isnull=True)
            tech_qs = tech_qs.filter(avito_profile__connection__isnull=True)
        choices = [(f"cd:{item.pk}", f"CD #{item.pk} · {item.sku or 'без артикула'} · {item.name}") for item in cd_qs[:500]]
        choices += [(f"tech:{item.pk}", f"Tech #{item.pk} · {item.sku or 'без артикула'} · {item.name}") for item in tech_qs[:500]]
        self.fields["product_ref"].choices = choices

    def clean_product_ref(self):
        value = self.cleaned_data["product_ref"]
        try:
            kind, raw_id = value.split(":", 1)
            product_id = int(raw_id)
            model = {"cd": CD, "tech": Tech}[kind]
        except (ValueError, KeyError) as exc:
            raise ValidationError("Некорректный товар.") from exc
        product = model.objects.active().filter(pk=product_id).first()
        if not product:
            raise ValidationError("Товар не найден.")
        if hasattr(product, "avito_profile") and hasattr(product.avito_profile, "connection"):
            raise ValidationError("Товар уже связан с объявлением Avito.")
        return kind, product
