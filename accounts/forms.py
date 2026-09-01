from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.db import transaction

from .models import PermissionSetMetadata, User


class CRMUserCreationForm(UserCreationForm):
    is_administrator = forms.BooleanField(label="Администратор", required=False)
    groups = forms.ModelMultipleChoiceField(
        label="Наборы прав", queryset=Group.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    user_permissions = forms.ModelMultipleChoiceField(
        label="Индивидуальные права", queryset=Permission.objects.select_related("content_type"),
        required=False, widget=forms.SelectMultiple(attrs={"size": 12}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username", "full_name", "phone_1", "phone_2", "phone_3", "email",
            "telegram", "verification_document", "is_active", "is_administrator",
            "groups", "user_permissions",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = self.cleaned_data["is_administrator"]
        user.is_staff = user.is_superuser
        if commit:
            user.save()
            self.save_m2m()
        return user


class CRMUserUpdateForm(forms.ModelForm):
    is_administrator = forms.BooleanField(label="Администратор", required=False)
    groups = forms.ModelMultipleChoiceField(
        label="Наборы прав", queryset=Group.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    user_permissions = forms.ModelMultipleChoiceField(
        label="Индивидуальные права", queryset=Permission.objects.select_related("content_type"),
        required=False, widget=forms.SelectMultiple(attrs={"size": 12}),
    )

    class Meta:
        model = User
        fields = (
            "username", "full_name", "phone_1", "phone_2", "phone_3", "email",
            "telegram", "verification_document", "is_active", "is_administrator", "groups", "user_permissions",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_administrator"].initial = self.instance.is_superuser

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = self.cleaned_data["is_administrator"]
        user.is_staff = user.is_superuser
        if commit:
            user.save()
            self.save_m2m()
        return user


class AdminPasswordResetForm(SetPasswordForm):
    pass


class PermissionSetForm(forms.ModelForm):
    description = forms.CharField(label="Описание", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    permissions = forms.ModelMultipleChoiceField(
        label="Права", queryset=Permission.objects.select_related("content_type"),
        required=False, widget=forms.SelectMultiple(attrs={"size": 18}),
    )

    class Meta:
        model = Group
        fields = ("name", "description", "permissions")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            metadata = getattr(self.instance, "gamebat_metadata", None)
            self.fields["description"].initial = metadata.description if metadata else ""

    @transaction.atomic
    def save(self, commit=True):
        group = super().save(commit=commit)
        if commit:
            PermissionSetMetadata.objects.update_or_create(
                group=group, defaults={"description": self.cleaned_data.get("description", "")}
            )
        return group
