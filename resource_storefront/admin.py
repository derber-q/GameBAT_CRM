from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    CollectionProduct, NewsCDProduct, NewsTechProduct, ProductCollection,
    StorefrontNews, StorefrontProduct, StorefrontSettings, StorefrontSubmission,
    WholesaleAccessLink, WholesaleContact, CatalogImageCrop, RetailSettings,
)


@admin.register(WholesaleContact)
class WholesaleContactAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "is_archived", "created_at")
    search_fields = ("name", "phone", "address")
    readonly_fields = ("created_at", "updated_at")
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WholesaleAccessLink)
class WholesaleAccessLinkAdmin(admin.ModelAdmin):
    list_display = ("contact", "is_active", "created_at", "created_by")
    readonly_fields = ("token_digest", "encrypted_token", "created_at", "created_by", "revoked_at")
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StorefrontSettings)
class StorefrontSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not StorefrontSettings.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return False


class CollectionProductInline(admin.TabularInline):
    model = CollectionProduct
    extra = 0


@admin.register(ProductCollection)
class ProductCollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "is_visible", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (CollectionProductInline,)


class NewsCDInline(admin.TabularInline):
    model = NewsCDProduct
    extra = 0


class NewsTechInline(admin.TabularInline):
    model = NewsTechProduct
    extra = 0


@admin.register(StorefrontNews)
class StorefrontNewsAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "published_at")
    list_filter = ("status",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = (NewsCDInline, NewsTechInline)


@admin.register(StorefrontProduct)
class StorefrontProductAdmin(admin.ModelAdmin):
    list_display = ("placement", "cd", "tech", "sort_order")


@admin.register(StorefrontSubmission)
class StorefrontSubmissionAdmin(admin.ModelAdmin):
    list_display = ("contact", "sale", "created_at")
    readonly_fields = ("contact", "idempotency_key", "cart_digest", "sale", "created_at")
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CatalogImageCrop)
class CatalogImageCropAdmin(admin.ModelAdmin):
    list_display = ("__str__", "position_x", "position_y", "zoom")
    search_fields = ("cd__name", "tech__name")
    autocomplete_fields = ("cd", "tech")
    readonly_fields = ("preview",)
    fields = ("cd", "tech", "position_x", "position_y", "zoom", "preview")

    class Media:
        js = ("resource/crop-preview.js",)

    @admin.display(description="Оригинал и кадр каталога")
    def preview(self, obj):
        if not obj or not obj.pk:
            return "Выберите товар и сохраните с продолжением редактирования, чтобы настроить кадр по предпросмотру."
        url = reverse("nomenclature:product_title_image", args=["cd" if obj.cd_id else "tech", obj.cd_id or obj.tech_id])
        return format_html('<div style="display:flex;flex-wrap:wrap;gap:20px"><a href="{}" target="_blank" rel="noopener"><img src="{}" alt="Полный оригинал" style="width:320px;max-width:100%;height:320px;object-fit:contain"></a><div style="width:240px;aspect-ratio:3/4;overflow:hidden;border-radius:12px"><img data-crop-preview src="{}" alt="Кадр каталога" style="width:100%;height:100%;object-fit:cover"></div></div><p>Параметры сразу меняют предпросмотр. После замены титульного фото старый кадр не применяется до повторного сохранения.</p>', url, url, url)


@admin.register(RetailSettings)
class RetailSettingsAdmin(admin.ModelAdmin):
    fields = ("warehouse", "price_source")

    def has_add_permission(self, request):
        return not RetailSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
