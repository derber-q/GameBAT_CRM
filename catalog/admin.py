from django.contrib import admin
from .models import Brand, CD, Platform, ProductType, Tech


@admin.register(Platform, Brand, ProductType)
class ReferenceAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(CD)
class CDAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "platform", "sku", "quantity", "quantity_on_consignment", "cost")
    list_filter = ("platform",)
    search_fields = ("name", "sku", "barcode", "cusa_ppsa_code")
    autocomplete_fields = ("platform",)
    readonly_fields = ("quantity_on_consignment",)


@admin.register(Tech)
class TechAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "brand", "product_type", "sku", "quantity", "quantity_on_consignment", "cost")
    list_filter = ("brand", "product_type")
    search_fields = ("name", "sku", "barcode")
    autocomplete_fields = ("brand", "product_type")
    readonly_fields = ("quantity_on_consignment",)
