import logging

from django.contrib import admin
from django.db import transaction

from .audit import changed_snapshots, product_snapshot, record_product_changes
from .models import (
    Brand,
    CD,
    Platform,
    ProductChangeEvent,
    ProductFieldChange,
    ProductType,
    Tech,
)
from .product_fields import PRICE_FIELDS, card_fields_for, field_permissions_for

logger = logging.getLogger("gamebat.business")


class ProductAdminMixin:
    def get_readonly_fields(self, request, obj=None):
        readonly = ["quantity_on_consignment", "cost"]
        for field, permission in field_permissions_for(self.model).items():
            enforce_permission = field in PRICE_FIELDS or obj is not None
            if enforce_permission and not (
                request.user.is_superuser or request.user.has_perm(permission)
            ):
                readonly.append(field)
        return tuple(readonly)

    def save_model(self, request, obj, form, change):
        audited_fields = card_fields_for(type(obj))
        with transaction.atomic():
            before = None
            if change and obj.pk:
                related_fields = ("platform",) if isinstance(obj, CD) else ("brand", "product_type")
                previous = type(obj).objects.select_for_update().select_related(*related_fields).get(pk=obj.pk)
                before = product_snapshot(previous, audited_fields)
            super().save_model(request, obj, form, change)
            if before is None:
                return
            changes = changed_snapshots(obj, before, audited_fields)
            try:
                record_product_changes(
                    actor=request.user,
                    instance=obj,
                    changes=changes,
                    source=ProductChangeEvent.Source.DJANGO_ADMIN,
                )
            except Exception:
                logger.exception(
                    "Ошибка сохранения истории товара из Django Admin: user_id=%s type=%s product_id=%s",
                    request.user.pk,
                    obj._meta.model_name,
                    obj.pk,
                )
                raise


@admin.register(Platform, Brand, ProductType)
class ReferenceAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(CD)
class CDAdmin(ProductAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "platform", "sku", "quantity_on_consignment", "cost", "retail_price")
    list_filter = ("platform",)
    search_fields = ("name", "sku", "barcode", "cusa_ppsa_code")
    autocomplete_fields = ("platform",)


@admin.register(Tech)
class TechAdmin(ProductAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "brand", "product_type", "sku", "quantity_on_consignment", "cost", "retail_price")
    list_filter = ("brand", "product_type")
    search_fields = ("name", "sku", "barcode")
    autocomplete_fields = ("brand", "product_type")


class ProductFieldChangeInline(admin.TabularInline):
    model = ProductFieldChange
    fields = ("field_label", "old_value", "new_value")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ReadonlyAuditAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductChangeEvent)
class ProductChangeEventAdmin(ReadonlyAuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "id", "created_at", "product_kind", "product_display", "actor", "source", "action_label"
    )
    list_filter = ("product_kind", "source", "action_kind", "created_at")
    search_fields = (
        "cd__name", "cd__sku", "tech__name", "tech__sku", "actor__username",
        "actor__full_name", "action_label",
    )
    readonly_fields = (
        "actor", "created_at", "source", "product_kind", "cd", "tech",
        "action_kind", "action_object_id", "action_label",
    )
    inlines = (ProductFieldChangeInline,)

    @admin.display(description="Товар")
    def product_display(self, obj):
        return obj.product


@admin.register(ProductFieldChange)
class ProductFieldChangeAdmin(ReadonlyAuditAdminMixin, admin.ModelAdmin):
    list_display = ("id", "event", "field_label", "old_value", "new_value")
    list_filter = ("event__product_kind", "event__source")
    search_fields = ("field_label", "old_value", "new_value", "event__cd__name", "event__tech__name")
    readonly_fields = ("event", "field_name", "field_label", "old_value", "new_value")
