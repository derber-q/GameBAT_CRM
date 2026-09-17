from django.contrib import admin

from .models import (
    AvitoListingConnection,
    AvitoProductPhoto,
    AvitoProductProfile,
    AvitoRemoteListing,
    AvitoSyncJob,
    AvitoSyncLog,
    IntegrationAuditEvent,
    IntegrationCredential,
)


@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ("provider", "status", "account_id", "last_checked_at", "updated_at")
    fields = (
        "provider", "status", "account_id", "account_name", "last_checked_at", "last_success_at",
        "last_error", "updated_at",
    )
    readonly_fields = (
        "provider", "account_id", "account_name",
        "status", "last_checked_at", "last_success_at", "last_error", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AvitoProductProfile)
class AvitoProductProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "product_kind", "product_id", "sell_on_avito", "sync_status", "updated_at")
    list_filter = ("sell_on_avito", "sync_status")
    search_fields = ("cd__name", "tech__name", "listing_title")


@admin.register(AvitoRemoteListing)
class AvitoRemoteListingAdmin(admin.ModelAdmin):
    list_display = ("avito_item_id", "title", "status", "remote_price", "last_seen_at", "missing_since")
    search_fields = ("=avito_item_id", "title")
    readonly_fields = ("snapshot", "last_seen_at", "missing_since")


@admin.register(AvitoListingConnection)
class AvitoListingConnectionAdmin(admin.ModelAdmin):
    list_display = ("remote_listing", "profile", "created_at", "updated_at")


@admin.register(AvitoProductPhoto)
class AvitoProductPhotoAdmin(admin.ModelAdmin):
    list_display = ("profile", "sort_order", "source", "created_at")


class ReadOnlyHistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AvitoSyncLog)
class AvitoSyncLogAdmin(ReadOnlyHistoryAdmin):
    list_display = ("started_at", "operation", "result", "profile", "http_status", "error_category")
    list_filter = ("result", "operation", "error_category")


@admin.register(IntegrationAuditEvent)
class IntegrationAuditEventAdmin(ReadOnlyHistoryAdmin):
    list_display = ("created_at", "action", "actor", "product_kind", "product_id")
    list_filter = ("action", "product_kind")


@admin.register(AvitoSyncJob)
class AvitoSyncJobAdmin(admin.ModelAdmin):
    list_display = ("dedupe_key", "job_type", "status", "run_after", "attempts")
    list_filter = ("job_type", "status")
    readonly_fields = ("dedupe_key", "job_type", "profile", "created_at", "updated_at")
