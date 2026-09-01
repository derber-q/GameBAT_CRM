from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError


class GameBATAdminAuthenticationForm(AdminAuthenticationForm):
    """Допускает к проверке admin сотрудников со специальным правом, не делая их staff."""
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError("Учётная запись неактивна.", code="inactive")
