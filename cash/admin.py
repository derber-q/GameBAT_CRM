from django.contrib import admin

from .models import CashRegister, CashTransaction, Safe


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "balance")
    search_fields = ("warehouse__name",)
    readonly_fields = ("warehouse", "balance")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Safe)
class SafeAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "balance")
    search_fields = ("warehouse__name",)
    readonly_fields = ("warehouse", "balance")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "cash_register", "operation_type", "source_label", "destination_label",
        "amount", "created_by", "created_at", "sale",
    )
    list_filter = ("operation_type", "cash_register__warehouse")
    search_fields = ("comment", "created_by__username", "sale__visible_id", "operation_key")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
