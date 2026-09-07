PRICE_FIELDS = ("retail_price", "wholesale_price", "yandex_market_price")

CD_CARD_FIELDS = (
    "platform",
    "name",
    "sku",
    "barcode",
    "cusa_ppsa_code",
    "description",
    "comment",
    *PRICE_FIELDS,
)

TECH_CARD_FIELDS = (
    "brand",
    "product_type",
    "name",
    "sku",
    "barcode",
    "description",
    "comment",
    *PRICE_FIELDS,
)

CD_FIELD_PERMISSIONS = {
    "platform": "catalog.change_cd_platform",
    "name": "catalog.change_cd_name",
    "description": "catalog.change_cd_description",
    "sku": "catalog.change_cd_sku",
    "barcode": "catalog.change_cd_barcode",
    "cusa_ppsa_code": "catalog.change_cd_cusa_ppsa_code",
    "comment": "catalog.change_cd_comment",
    "retail_price": "pricing.change_retail_price",
    "wholesale_price": "pricing.change_wholesale_price",
    "yandex_market_price": "pricing.change_yandex_market_price",
}

TECH_FIELD_PERMISSIONS = {
    "brand": "catalog.change_tech_brand",
    "product_type": "catalog.change_tech_product_type",
    "name": "catalog.change_tech_name",
    "description": "catalog.change_tech_description",
    "sku": "catalog.change_tech_sku",
    "barcode": "catalog.change_tech_barcode",
    "comment": "catalog.change_tech_comment",
    "retail_price": "pricing.change_retail_price",
    "wholesale_price": "pricing.change_wholesale_price",
    "yandex_market_price": "pricing.change_yandex_market_price",
}


def card_fields_for(model):
    return CD_CARD_FIELDS if model._meta.model_name == "cd" else TECH_CARD_FIELDS


def field_permissions_for(model):
    return CD_FIELD_PERMISSIONS if model._meta.model_name == "cd" else TECH_FIELD_PERMISSIONS
