PRICE_FIELDS = ("avito_price", "wholesale_price", "yandex_market_price")
MARKUP_FIELDS = ("avito_markup_from_wholesale", "yandex_markup_from_wholesale")
PRICING_FIELDS = (*PRICE_FIELDS, *MARKUP_FIELDS)
MARKETPLACE_CARD_FIELDS = ("length_cm", "width_cm", "height_cm", "yandex_desired_profit", "yandex_pricing_integration", "yandex_pricing_category")

CD_CARD_FIELDS = (
    "platform",
    "game_series",
    "name",
    "sku",
    "cusa_ppsa_code",
    "weight_grams",
    "description",
    "comment",
    "exclude_from_supplier_template",
    *MARKETPLACE_CARD_FIELDS,
    *PRICING_FIELDS,
)

TECH_CARD_FIELDS = (
    "brand",
    "product_type",
    "name",
    "sku",
    "weight_grams",
    "description",
    "comment",
    "exclude_from_supplier_template",
    *MARKETPLACE_CARD_FIELDS,
    *PRICING_FIELDS,
)

CD_FIELD_PERMISSIONS = {
    "platform": "catalog.change_cd_platform",
    "game_series": "catalog.change_cd_game_series",
    "name": "catalog.change_cd_name",
    "description": "catalog.change_cd_description",
    "sku": "catalog.change_cd_sku",
    "weight_grams": "catalog.change_cd_weight",
    "cusa_ppsa_code": "catalog.change_cd_cusa_ppsa_code",
    "comment": "catalog.change_cd_comment",
    "exclude_from_supplier_template": "catalog.change_cd",
    "length_cm": "catalog.change_cd_weight",
    "width_cm": "catalog.change_cd_weight",
    "height_cm": "catalog.change_cd_weight",
    "yandex_desired_profit": "pricing.change_yandex_market_price",
    "yandex_pricing_integration": "pricing.change_yandex_market_price",
    "yandex_pricing_category": "pricing.change_yandex_market_price",
    "avito_price": "pricing.change_retail_price",
    "wholesale_price": "pricing.change_wholesale_price",
    "yandex_market_price": "pricing.change_yandex_market_price",
    "avito_markup_from_wholesale": "pricing.change_retail_price",
    "yandex_markup_from_wholesale": "pricing.change_yandex_market_price",
}

TECH_FIELD_PERMISSIONS = {
    "brand": "catalog.change_tech_brand",
    "product_type": "catalog.change_tech_product_type",
    "name": "catalog.change_tech_name",
    "description": "catalog.change_tech_description",
    "sku": "catalog.change_tech_sku",
    "weight_grams": "catalog.change_tech_weight",
    "comment": "catalog.change_tech_comment",
    "exclude_from_supplier_template": "catalog.change_tech",
    "length_cm": "catalog.change_tech_weight",
    "width_cm": "catalog.change_tech_weight",
    "height_cm": "catalog.change_tech_weight",
    "yandex_desired_profit": "pricing.change_yandex_market_price",
    "yandex_pricing_integration": "pricing.change_yandex_market_price",
    "yandex_pricing_category": "pricing.change_yandex_market_price",
    "avito_price": "pricing.change_retail_price",
    "wholesale_price": "pricing.change_wholesale_price",
    "yandex_market_price": "pricing.change_yandex_market_price",
    "avito_markup_from_wholesale": "pricing.change_retail_price",
    "yandex_markup_from_wholesale": "pricing.change_yandex_market_price",
}


def card_fields_for(model):
    return CD_CARD_FIELDS if model._meta.model_name == "cd" else TECH_CARD_FIELDS


def field_permissions_for(model):
    return CD_FIELD_PERMISSIONS if model._meta.model_name == "cd" else TECH_FIELD_PERMISSIONS
