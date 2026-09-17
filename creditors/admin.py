import logging

from django.contrib import admin

from .models import Creditor, CreditorTransaction

logger = logging.getLogger("gamebat.business")


@admin.register(Creditor)
class CreditorAdmin(admin.ModelAdmin):
    list_display = ("name", "current_debt", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("current_debt", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        logger.info(
            "Кредитор сохранён через Admin: user_id=%s creditor_id=%s fields=%s",
            request.user.pk, obj.pk, ",".join(form.changed_data),
        )


@admin.register(CreditorTransaction)
class CreditorTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "creditor", "old_debt", "new_debt", "delta",
        "warehouse", "money_source_type", "amount", "actor",
    )
    list_filter = ("money_source_type", "warehouse")
    search_fields = ("creditor__name", "comment", "actor__username")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
