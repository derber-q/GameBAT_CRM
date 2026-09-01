from django import forms
from .models import Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "name", "letter", "highlight_color", "legal_entity", "email", "phone_1",
            "phone_2", "phone_3", "website", "telegram",
        )
        widgets = {"highlight_color": forms.TextInput(attrs={"type": "color"})}
