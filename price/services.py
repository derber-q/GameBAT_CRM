import logging
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.db import transaction
from django.db.models import Q

from catalog.models import ProductChangeEvent, ProductType, Tech
from catalog.audit import field_change, record_product_changes
from catalog.product_identifiers import set_product_weight
from catalog.supplier_exclusions import exclusion_keys
from pricing.models import SupplierCDPrice, SupplierTechPrice

from .models import ProcurementPriceList, ProcurementPriceListItem, ProcurementPricePreference, ProcurementSupplierOffer
from .postpayment_rules import tech_postpayment_surcharge
from .procurement_suppliers import apply_supplier_choice

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")
RATE_PRECISION = Decimal("0.000001")


def decimal_value(value, *, precision=CENT, positive=False, nonnegative=False, label="Значение"):
    try:
        result = Decimal(str(value)).quantize(precision, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{label}: укажите корректное число.") from exc
    if not result.is_finite():
        raise ValidationError(f"{label}: укажите корректное число.")
    if positive and result <= 0:
        raise ValidationError(f"{label} должно быть больше нуля.")
    if nonnegative and result < 0:
        raise ValidationError(f"{label} не может быть отрицательным.")
    return result


def validated_postpayment_surcharge(value):
    result = decimal_value(value, nonnegative=True, label="Доплата за постоплату")
    DecimalValidator(max_digits=20, decimal_places=2)(Decimal(str(value)))
    return result


def calculate_postpayment(prepayment, *, surcharge=None):
    price = decimal_value(prepayment, nonnegative=True, label="Цена предоплаты")
    if surcharge is not None:
        surcharge = validated_postpayment_surcharge(surcharge)
    elif price < Decimal("2000"):
        surcharge = Decimal("60")
    elif price < Decimal("3000"):
        surcharge = Decimal("80")
    else:
        surcharge = Decimal("100")
    return (price + surcharge).quantize(CENT, rounding=ROUND_HALF_UP)


def round_customer_price(value):
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Покупательская цена: укажите корректное число.') from exc
    if not price.is_finite() or price < 0:
        raise ValidationError('Покупательская цена должна быть неотрицательной.')
    return ((price / Decimal('10')).to_integral_value(rounding=ROUND_CEILING) * Decimal('10')).quantize(CENT)


def rounded_customer_prices(prepayment, *, surcharge=None):
    raw_pre = decimal_value(prepayment, nonnegative=True, label='Цена предоплаты')
    raw_post = calculate_postpayment(raw_pre, surcharge=surcharge)
    pre, post = round_customer_price(raw_pre), round_customer_price(raw_post)
    return pre, post, pre - raw_pre, post - raw_post


def calculate_prepayment(postpayment, *, surcharge=None, rounded=False):
    price = decimal_value(postpayment, nonnegative=True, label="Цена постоплаты")
    if surcharge is not None:
        surcharge = validated_postpayment_surcharge(surcharge)
        if price < surcharge:
            raise ValidationError("Цена постоплаты не может быть меньше доплаты за постоплату.")
        return price - surcharge
    # На границах тарифов есть разрывы: не каждая постоплата имеет обратную цену.
    for surcharge in (Decimal("60"), Decimal("80"), Decimal("100")):
        prepayment = price - surcharge
        if prepayment >= 0 and calculate_postpayment(prepayment) == price:
            return prepayment
    if rounded:
        # Округление делает достижимыми края разрывов 2060 и 3080,
        # сохраняя прежнее правило выбора доплаты по исходной предоплате.
        for candidate in (Decimal('1999.99'), Decimal('2999.99')):
            original_post = calculate_postpayment(candidate)
            if original_post <= price and round_customer_price(original_post) == round_customer_price(price):
                return candidate
    raise ValidationError(
        "Цена постоплаты не соответствует правилу расчёта. Допустимо: от 60 до 2059,99 RUB, "
        "от 2080 до 3079,99 RUB или от 3100 RUB."
    )


def _supplier_offers(*, lock=False):
    queryset_method = "select_for_update" if lock else "all"
    result = defaultdict(list)
    for kind, model, field in (
        (ProcurementPriceListItem.ProductKind.CD, SupplierCDPrice, "cd"),
        (ProcurementPriceListItem.ProductKind.TECH, SupplierTechPrice, "tech"),
    ):
        relations = ("supplier", field, "tech__product_type", "tech__brand") if field == "tech" else ("supplier", field)
        queryset = getattr(model.objects, queryset_method)().select_related(*relations).filter(price__gt=0)
        for offer in queryset.order_by("supplier_id", f"{field}_id"):
            product = getattr(offer, field)
            if product.is_archived:
                continue
            result[(kind, product.pk)].append((offer.supplier, offer.price, product))
    return result


def resolve_best_suppliers(offers=None):
    offers = offers if offers is not None else _supplier_offers()
    excluded = exclusion_keys(offers)
    minimum_candidates = {}
    unique_wins = Counter()
    for key, product_offers in offers.items():
        product_offers = [row for row in product_offers if (*key, row[0].pk) not in excluded]
        if not product_offers:
            continue
        minimum = min(price for _, price, _ in product_offers)
        candidates = [(supplier, price, product) for supplier, price, product in product_offers if price == minimum]
        minimum_candidates[key] = candidates
        if len(candidates) == 1:
            unique_wins[candidates[0][0].pk] += 1

    winners = {}
    for key, candidates in minimum_candidates.items():
        winners[key] = sorted(
            candidates,
            key=lambda row: (row[0].priority, row[0].name.casefold(), row[0].pk),
        )[0]
    return winners, unique_wins


class MissingProcurementWeights(ValidationError):
    def __init__(self, products):
        self.products = sorted(products, key=lambda product: (product.product_type.name, product.name, product.pk))
        super().__init__("Перед созданием закупочного прайса укажите вес всей участвующей техники.")


def get_missing_procurement_weights():
    winners, _ = resolve_best_suppliers()
    return sorted(
        (product for (kind, _), (_, _, product) in winners.items() if kind == "tech" and not product.weight_grams),
        key=lambda product: (product.product_type.name, product.name, product.pk),
    )


def _price_preferences(product_keys, *, lock=False):
    keys = list(product_keys)
    queryset = ProcurementPricePreference.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    queryset = queryset.filter(
        Q(cd_id__in=[pk for kind, pk in keys if kind == "cd"])
        | Q(tech_id__in=[pk for kind, pk in keys if kind == "tech"])
    )
    return {("cd", row.cd_id) if row.cd_id else ("tech", row.tech_id): row for row in queryset}


class MissingProcurementSurcharges(ValidationError):
    def __init__(self, products):
        self.products = sorted(products, key=lambda product: (product.product_type.name, product.name, product.pk))
        super().__init__("Укажите доплату за постоплату для техники без согласованной ставки.")


def get_missing_procurement_surcharges():
    winners, _ = resolve_best_suppliers()
    preferences = _price_preferences(winners)
    return sorted([
        product for (kind, pk), (_, _, product) in winners.items()
        if kind == "tech" and (preferences.get((kind, pk)) is None or preferences[(kind, pk)].postpayment_surcharge_rub is None)
        and tech_postpayment_surcharge(product) is None
    ], key=lambda product: (product.product_type.name, product.name, product.pk))


def _prepare_procurement_weights(*, winners, weights, actor):
    tech_ids = [product_id for kind, product_id in winners if kind == "tech"]
    products = {
        product.pk: product for product in Tech.objects.active().select_for_update().select_related("product_type").filter(pk__in=tech_ids)
    }
    if len(products) != len(tech_ids):
        raise ValidationError("Состав техники изменился. Повторите создание прайса.")
    weights = weights or {}
    if not set(weights).issubset(products):
        raise ValidationError("Передан вес товара, который не участвует в закупочном прайсе.")
    missing = [product for product in products.values() if not product.weight_grams]
    if any(product.pk not in weights for product in missing):
        raise MissingProcurementWeights(missing)
    for product in products.values():
        if product.weight_grams:
            continue
        if not (actor.is_superuser or actor.has_perm("catalog.change_tech_weight")):
            raise ValidationError("Для ввода веса необходимо право изменения веса техники.")
        try:
            weight = Decimal(str(weights[product.pk]))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError(f"{product.name}: укажите вес целым числом граммов.") from exc
        if not weight.is_finite() or weight <= 0 or weight != weight.to_integral_value() or weight > 2147483647:
            raise ValidationError(f"{product.name}: вес должен быть целым числом от 1 до 2147483647 г.")
        updated = set_product_weight(
            actor=actor, product_kind="tech", product_id=product.pk, weight_grams=int(weight),
        )
        product.weight_grams = updated.weight_grams
        logger.info("Вес для закупочного прайса сохранён: user_id=%s tech_id=%s weight_grams=%s", actor.pk, product.pk, product.weight_grams)
    return products


def weighted_procurement_delivery(*, weight_grams, tariff, dollar_rate, label='Доставка'):
    """Действующая весовая формула для прайса и сохранённых расчётов операций рейса."""
    return decimal_value(Decimal(weight_grams) / Decimal('1000') * tariff * dollar_rate,
                         nonnegative=True, label=label)


def procurement_delivery(*, product, kind, price_list):
    """Единый расчёт доставки единицы по зафиксированным тарифам прайса."""
    if kind == 'cd':
        if price_list.delivery_cd_rub is None:
            raise ValidationError('В прайсе не сохранена доставка диска.')
        return decimal_value(price_list.delivery_cd_rub, nonnegative=True), '', None
    group = product.product_type.procurement_delivery_group
    rates = {
        ProductType.DeliveryGroup.GENERAL: price_list.delivery_general_usdt_per_kg,
        ProductType.DeliveryGroup.DEVICES: price_list.delivery_devices_usdt_per_kg,
        ProductType.DeliveryGroup.STORAGE: price_list.delivery_storage_usdt_per_kg,
    }
    tariff = rates.get(group)
    if tariff is None or not product.weight_grams or not price_list.exchange_rate_usdt_rub:
        raise ValidationError(f'{product.name}: для доставки нужны вес, сохранённый тариф и курс USDT/RUB.')
    delivery = weighted_procurement_delivery(weight_grams=product.weight_grams, tariff=tariff,
        dollar_rate=price_list.exchange_rate_usdt_rub, label=f'{product.name}: доставка')
    return delivery, group, tariff


@transaction.atomic
def create_procurement_price_list(
    *, actor, exchange_rate_usdt_aed, exchange_rate_usdt_rub,
    delivery_general_usdt_per_kg, delivery_devices_usdt_per_kg, delivery_storage_usdt_per_kg,
    delivery_cd_rub, weights=None, postpayment_surcharges=None,
):
    rate_usdt_aed = decimal_value(
        exchange_rate_usdt_aed, precision=RATE_PRECISION, positive=True,
        label="Курс AED → USDT (AED за 1 USDT)",
    )
    rate_usdt_rub = decimal_value(
        exchange_rate_usdt_rub, precision=RATE_PRECISION, positive=True,
        label="Курс USDT → RUB (RUB за 1 USDT)",
    )
    validate_rate = DecimalValidator(max_digits=20, decimal_places=6)
    validate_rate(rate_usdt_aed)
    validate_rate(rate_usdt_rub)
    rate = decimal_value(
        rate_usdt_rub / rate_usdt_aed, precision=RATE_PRECISION, positive=True,
        label="Расчётный курс AED → RUB",
    )
    validate_rate(rate)
    delivery_rates = {}
    for group, value in (
        (ProductType.DeliveryGroup.GENERAL, delivery_general_usdt_per_kg),
        (ProductType.DeliveryGroup.DEVICES, delivery_devices_usdt_per_kg),
        (ProductType.DeliveryGroup.STORAGE, delivery_storage_usdt_per_kg),
    ):
        delivery_rates[group] = decimal_value(
            value, precision=RATE_PRECISION, nonnegative=True, label="Тариф доставки, USDT за кг",
        )
        validate_rate(delivery_rates[group])
    cd_delivery = decimal_value(delivery_cd_rub, nonnegative=True, label="Доставка одного диска, RUB")
    DecimalValidator(max_digits=20, decimal_places=2)(cd_delivery)
    offers = _supplier_offers(lock=True)
    if not offers:
        raise ValidationError("Нет ни одной положительной актуальной цены поставщика.")
    winners, _ = resolve_best_suppliers(offers)
    if not winners:
        raise ValidationError('Нет доступных предложений: все поставщики исключены из подбора участвующих товаров.')
    tech_products = _prepare_procurement_weights(winners=winners, weights=weights, actor=actor)
    preferences = _price_preferences(winners)
    postpayment_surcharges = postpayment_surcharges or {}
    if not set(postpayment_surcharges).issubset({pk for kind, pk in winners if kind == "tech"}):
        raise ValidationError("Передана доплата товара, который не участвует в закупочном прайсе.")
    surcharges = {}
    custom_surcharge_ids = set()
    missing_surcharges = []
    for (kind, pk), (_, _, product) in winners.items():
        preference = preferences.get((kind, pk))
        surcharge = preference.postpayment_surcharge_rub if preference else None
        if kind == "tech" and surcharge is None:
            if pk in postpayment_surcharges:
                if not (actor.is_superuser or actor.has_perm("price.change_procurement_markup")):
                    raise ValidationError("Для ввода доплаты за постоплату необходимо право изменения наценки.")
                surcharge = validated_postpayment_surcharge(postpayment_surcharges[pk])
                custom_surcharge_ids.add(pk)
            else:
                surcharge = tech_postpayment_surcharge(product)
            if surcharge is None:
                missing_surcharges.append(product)
        surcharges[(kind, pk)] = surcharge
    if missing_surcharges:
        raise MissingProcurementSurcharges(missing_surcharges)
    price_list = ProcurementPriceList.objects.create(
        supplier_offers_complete=True,
        exchange_rate_usdt_aed=rate_usdt_aed, exchange_rate_usdt_rub=rate_usdt_rub,
        exchange_rate_aed_rub=rate, created_by=actor,
        delivery_general_usdt_per_kg=delivery_rates[ProductType.DeliveryGroup.GENERAL],
        delivery_devices_usdt_per_kg=delivery_rates[ProductType.DeliveryGroup.DEVICES],
        delivery_storage_usdt_per_kg=delivery_rates[ProductType.DeliveryGroup.STORAGE],
        delivery_cd_rub=cd_delivery,
    )
    items = []
    for (kind, _), (supplier, supplier_price, product) in winners.items():
        if kind == "tech":
            product = tech_products[product.pk]
        delivery, delivery_group, delivery_rate = procurement_delivery(product=product, kind=kind, price_list=price_list)
        # Промежуточную сумму в USDT не округляем; рубли округляются один раз до копеек.
        base = decimal_value(supplier_price / rate_usdt_aed * rate_usdt_rub, nonnegative=True, label="База, RUB")
        DecimalValidator(max_digits=20, decimal_places=2)(base)
        preference = preferences.get((kind, product.pk))
        markup = preference.markup_rub if preference else Decimal("0.00")
        prepayment = base + delivery + markup
        if prepayment < 0:
            raise ValidationError(
                f"{product.name}: сохранённая наценка даёт отрицательную итоговую цену. "
                "Измените наценку в предыдущем прайсе и повторите создание."
            )
        surcharge = surcharges[(kind, product.pk)]
        raw_markup = markup
        prepayment, postpayment, pre_extra, post_extra = rounded_customer_prices(prepayment, surcharge=surcharge)
        markup = prepayment - base - delivery
        for amount in (markup, delivery, prepayment, postpayment):
            DecimalValidator(max_digits=20, decimal_places=2)(amount)
        values = {
            "price_list": price_list,
            "product_kind": kind,
            "product_name_snapshot": product.name,
            "article_snapshot": product.sku,
            "selected_supplier": supplier,
            "supplier_price_aed": supplier_price,
            "exchange_rate_aed_rub": rate,
            "base_price_rub": base,
            "markup_rub": markup,
            'original_markup_rub': raw_markup,
            'prepayment_rounding_extra_rub': pre_extra,
            'postpayment_rounding_extra_rub': post_extra,
            "delivery_rub": delivery,
            "weight_grams_snapshot": product.weight_grams,
            "delivery_group_snapshot": delivery_group,
            "delivery_usdt_per_kg_snapshot": delivery_rate,
            "prepayment_price_rub": prepayment,
            "postpayment_price_rub": postpayment,
            "postpayment_surcharge_rub": surcharge,
            kind: product,
        }
        items.append(ProcurementPriceListItem(**values))
    ProcurementPriceListItem.objects.bulk_create(items)
    ProcurementSupplierOffer.objects.bulk_create([
        ProcurementSupplierOffer(price_list_item=item, supplier=supplier, price_aed=price)
        for item in items for supplier, price, _ in offers[(item.product_kind, item.product_id)]
    ])
    for item in items:
        if item.product_kind == "tech" and item.tech_id in custom_surcharge_ids:
            preference = preferences.get(("tech", item.tech_id)) or ProcurementPricePreference(tech_id=item.tech_id)
            preference.markup_rub = item.configured_markup_rub
            preference.postpayment_surcharge_rub = item.postpayment_surcharge_rub
            preference.source_item = item
            preference.updated_by = actor
            preference.save()
    logger.info(
        "Закупочный прайс создан: user_id=%s price_list_id=%s usdt_aed=%s usdt_rub=%s rate=%s items=%s",
        actor.pk, price_list.pk, rate_usdt_aed, rate_usdt_rub, rate, len(items),
    )
    price_list.unavailable_products = [rows[0][2] for key, rows in offers.items() if key not in winners]
    return price_list


class NegativeProcurementMarkup(ValidationError):
    def __init__(self, items):
        self.items = items
        super().__init__("В прайсе есть отрицательная наценка. Подтвердите сохранение этих цен.")


@transaction.atomic
def backfill_procurement_tech_surcharges(*, actor, price_list_id, apply=False):
    """Перенос старых строк Tech на согласованные ставки без изменения остальных ценовых составляющих."""
    if not (actor.is_superuser or actor.has_perm("price.change_procurement_markup")):
        raise ValidationError("У вас нет права изменять доплату за постоплату.")
    try:
        price_list = ProcurementPriceList.objects.select_for_update().get(pk=price_list_id)
    except ProcurementPriceList.DoesNotExist as exc:
        raise ValidationError("Закупочный прайс не найден.") from exc
    if price_list.customer_orders.exists():
        raise ValidationError("Прайс уже использован в заказе; его ценовой снимок изменять нельзя.")
    items = list(price_list.items.select_for_update().filter(
        product_kind="tech", postpayment_surcharge_rub__isnull=True,
    ).select_related("tech__brand", "tech__product_type"))
    changes = []
    missing = []
    for item in items:
        surcharge = tech_postpayment_surcharge(item.tech)
        if surcharge is None:
            missing.append(item.tech)
            continue
        postpayment = calculate_postpayment(item.prepayment_price_rub, surcharge=surcharge)
        changes.append({
            "item_id": item.pk, "tech_id": item.tech_id,
            "old_surcharge": item.effective_postpayment_surcharge_rub, "new_surcharge": surcharge,
            "old_postpayment": item.postpayment_price_rub, "new_postpayment": postpayment,
        })
        item.postpayment_surcharge_rub = surcharge
        item.postpayment_price_rub = postpayment
        item.full_clean()
    if missing:
        raise MissingProcurementSurcharges(missing)
    if apply:
        for item, change in zip(items, changes):
            item.save(update_fields=("postpayment_surcharge_rub", "postpayment_price_rub"))
            logger.info(
                "Исправлена доплата старого прайса Tech: user_id=%s price_list_id=%s item_id=%s old=%s new=%s",
                actor.pk, price_list.pk, item.pk, change["old_surcharge"], change["new_surcharge"],
            )
    return changes


@transaction.atomic
def update_procurement_pricing(
    *, actor, price_list_id, rows, can_change_markup, can_change_delivery, negative_markup_confirmed=False,
):
    try:
        price_list = ProcurementPriceList.objects.select_for_update().get(pk=price_list_id)
    except ProcurementPriceList.DoesNotExist as exc:
        raise ValidationError("Закупочный прайс не найден.") from exc
    if price_list.customer_orders.exists():
        raise ValidationError("Прайс уже использован в заказе; его ценовой снимок изменять нельзя.")
    items = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.select_for_update().filter(price_list=price_list)
            .select_related('selected_supplier', 'cd', 'tech').prefetch_related('supplier_offers__supplier')
    }
    if set(rows) != set(items):
        raise ValidationError("Состав закупочного прайса изменён или передан не полностью.")
    surcharge_changes = {}
    supplier_changes = {}
    excluded = exclusion_keys((item.product_kind, item.product_id) for item in items.values())
    for item_id, values in rows.items():
        item = items[item_id]
        before_supplier = apply_supplier_choice(item, price_list, values, actor, excluded)
        if before_supplier is not None:
            supplier_changes[item_id] = before_supplier
        delivery = decimal_value(values.get("delivery"), nonnegative=True, label="Доставка")
        original_surcharge = None if item.postpayment_surcharge_mode == "tiered" else item.effective_postpayment_surcharge_rub
        surcharge = original_surcharge
        if "postpayment_surcharge" in values:
            entered_surcharge = validated_postpayment_surcharge(values["postpayment_surcharge"])
            mode = values.get("surcharge_mode", "fixed")
            if mode == "tiered" and item.product_kind == "cd":
                surcharge = None
            elif mode == "fixed":
                surcharge = entered_surcharge
            else:
                raise ValidationError("Некорректный режим доплаты за постоплату.")
        if surcharge != original_surcharge and not can_change_markup:
            raise ValidationError("У вас нет права изменять доплату за постоплату.")
        if surcharge != original_surcharge:
            surcharge_changes[item_id] = surcharge
        source = values.get("price_source", "markup")
        if source == "prepayment":
            prepayment = decimal_value(values.get("prepayment"), nonnegative=True, label="Цена предоплаты")
        elif source == "postpayment":
            prepayment = calculate_prepayment(values.get("postpayment"), surcharge=surcharge, rounded=True)
        elif source == "markup":
            markup = decimal_value(values.get("markup"), label="Наценка")
            prepayment = item.base_price_rub + markup + delivery
        else:
            raise ValidationError("Неизвестный способ изменения цены закупочного прайса.")
        markup = prepayment - item.base_price_rub - delivery
        if not can_change_markup and markup != item.configured_markup_rub:
            raise ValidationError("У вас нет права изменять наценку.")
        if not can_change_delivery and delivery != item.delivery_rub:
            raise ValidationError("У вас нет права изменять доставку.")
        prepayment = (item.base_price_rub + markup + delivery).quantize(CENT, rounding=ROUND_HALF_UP)
        item.original_markup_rub = markup
        item.delivery_rub = delivery
        item.postpayment_surcharge_rub = surcharge
        item.prepayment_price_rub, item.postpayment_price_rub, item.prepayment_rounding_extra_rub, item.postpayment_rounding_extra_rub = rounded_customer_prices(prepayment, surcharge=surcharge)
        item.markup_rub = item.prepayment_price_rub - item.base_price_rub - delivery
        item.full_clean()
    negative_items = [item for item in items.values() if item.configured_markup_rub < 0]
    if negative_items and negative_markup_confirmed is not True:
        raise NegativeProcurementMarkup(negative_items)
    preferences = _price_preferences(((item.product_kind, item.product_id) for item in items.values()), lock=True)
    for item in items.values():
        item.save(update_fields=(
            "markup_rub", "original_markup_rub", 'prepayment_rounding_extra_rub', 'postpayment_rounding_extra_rub',
            "delivery_rub", "prepayment_price_rub", "postpayment_price_rub", "postpayment_surcharge_rub",
            "selected_supplier", "supplier_price_aed", "base_price_rub",
        ))
        if item.pk in supplier_changes:
            old_supplier, old_price, old_base = supplier_changes[item.pk]
            record_product_changes(actor=actor, instance=item.product, source=ProductChangeEvent.Source.CRM,
                changes=[
                    field_change(field_name=f'procurement_supplier_{price_list.pk}',
                        field_label=f'Поставщик закупочного прайса №{price_list.pk}',
                        old_value=old_supplier, new_value=item.selected_supplier_id),
                    field_change(field_name=f'procurement_supplier_price_{price_list.pk}',
                        field_label='Сохранённая закупочная цена AED', old_value=old_price, new_value=item.supplier_price_aed),
                    field_change(field_name=f'procurement_base_{price_list.pk}',
                        field_label='База закупки RUB', old_value=old_base, new_value=item.base_price_rub),
                ])
        preference = preferences.get((item.product_kind, item.product_id))
        if preference is None:
            preference = ProcurementPricePreference(**{f"{item.product_kind}_id": item.product_id})
        preference.markup_rub = item.configured_markup_rub
        # Старая ставка снимка не становится ручным правилом без её изменения сотрудником.
        if item.pk in surcharge_changes:
            preference.postpayment_surcharge_rub = surcharge_changes[item.pk]
        preference.source_item = item
        preference.updated_by = actor
        preference.save()
    logger.info(
        "Закупочный прайс пересчитан: user_id=%s price_list_id=%s items=%s",
        actor.pk, price_list.pk, len(items),
    )
    return price_list
