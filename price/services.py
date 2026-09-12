import logging
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from pricing.models import SupplierCDPrice, SupplierTechPrice

from .models import ProcurementPriceList, ProcurementPriceListItem

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")
RATE_PRECISION = Decimal("0.000001")


def decimal_value(value, *, precision=CENT, positive=False, nonnegative=False, label="Значение"):
    try:
        result = Decimal(str(value)).quantize(precision, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{label}: укажите корректное число.") from exc
    if positive and result <= 0:
        raise ValidationError(f"{label} должно быть больше нуля.")
    if nonnegative and result < 0:
        raise ValidationError(f"{label} не может быть отрицательным.")
    return result


def calculate_postpayment(prepayment):
    price = decimal_value(prepayment, nonnegative=True, label="Цена предоплаты")
    if price < Decimal("2000"):
        surcharge = Decimal("60")
    elif price < Decimal("3000"):
        surcharge = Decimal("80")
    else:
        surcharge = Decimal("100")
    return (price + surcharge).quantize(CENT, rounding=ROUND_HALF_UP)


def _supplier_offers(*, lock=False):
    queryset_method = "select_for_update" if lock else "all"
    result = defaultdict(list)
    for kind, model, field in (
        (ProcurementPriceListItem.ProductKind.CD, SupplierCDPrice, "cd"),
        (ProcurementPriceListItem.ProductKind.TECH, SupplierTechPrice, "tech"),
    ):
        queryset = getattr(model.objects, queryset_method)().select_related("supplier", field).filter(price__gt=0)
        for offer in queryset.order_by("supplier_id", f"{field}_id"):
            product = getattr(offer, field)
            result[(kind, product.pk)].append((offer.supplier, offer.price, product))
    return result


def resolve_best_suppliers(offers=None):
    offers = offers if offers is not None else _supplier_offers()
    minimum_candidates = {}
    unique_wins = Counter()
    for key, product_offers in offers.items():
        minimum = min(price for _, price, _ in product_offers)
        candidates = [(supplier, price, product) for supplier, price, product in product_offers if price == minimum]
        minimum_candidates[key] = candidates
        if len(candidates) == 1:
            unique_wins[candidates[0][0].pk] += 1

    winners = {}
    for key, candidates in minimum_candidates.items():
        winners[key] = sorted(
            candidates,
            key=lambda row: (-unique_wins[row[0].pk], row[0].name.casefold(), row[0].pk),
        )[0]
    return winners, unique_wins


@transaction.atomic
def create_procurement_price_list(*, actor, exchange_rate):
    rate = decimal_value(
        exchange_rate, precision=RATE_PRECISION, positive=True, label="Курс AED → RUB"
    )
    offers = _supplier_offers(lock=True)
    if not offers:
        raise ValidationError("Нет ни одной положительной актуальной цены поставщика.")
    winners, _ = resolve_best_suppliers(offers)
    price_list = ProcurementPriceList.objects.create(exchange_rate_aed_rub=rate, created_by=actor)
    items = []
    for (kind, _), (supplier, supplier_price, product) in winners.items():
        base = (supplier_price * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        values = {
            "price_list": price_list,
            "product_kind": kind,
            "product_name_snapshot": product.name,
            "article_snapshot": product.sku,
            "selected_supplier": supplier,
            "supplier_price_aed": supplier_price,
            "exchange_rate_aed_rub": rate,
            "base_price_rub": base,
            "markup_rub": Decimal("0"),
            "delivery_rub": Decimal("0"),
            "prepayment_price_rub": base,
            "postpayment_price_rub": calculate_postpayment(base),
            kind: product,
        }
        items.append(ProcurementPriceListItem(**values))
    ProcurementPriceListItem.objects.bulk_create(items)
    logger.info(
        "Закупочный прайс создан: user_id=%s price_list_id=%s rate=%s items=%s",
        actor.pk, price_list.pk, rate, len(items),
    )
    return price_list


@transaction.atomic
def update_procurement_pricing(*, actor, price_list_id, rows, can_change_markup, can_change_delivery):
    try:
        price_list = ProcurementPriceList.objects.select_for_update().get(pk=price_list_id)
    except ProcurementPriceList.DoesNotExist as exc:
        raise ValidationError("Закупочный прайс не найден.") from exc
    if price_list.customer_orders.exists():
        raise ValidationError("Прайс уже использован в заказе; его ценовой снимок изменять нельзя.")
    items = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.select_for_update().filter(price_list=price_list)
    }
    if set(rows) != set(items):
        raise ValidationError("Состав закупочного прайса изменён или передан не полностью.")
    for item_id, values in rows.items():
        item = items[item_id]
        markup = decimal_value(values.get("markup"), nonnegative=True, label="Наценка")
        delivery = decimal_value(values.get("delivery"), nonnegative=True, label="Доставка")
        if not can_change_markup and markup != item.markup_rub:
            raise ValidationError("У вас нет права изменять наценку.")
        if not can_change_delivery and delivery != item.delivery_rub:
            raise ValidationError("У вас нет права изменять доставку.")
        prepayment = (item.base_price_rub + markup + delivery).quantize(CENT, rounding=ROUND_HALF_UP)
        item.markup_rub = markup
        item.delivery_rub = delivery
        item.prepayment_price_rub = prepayment
        item.postpayment_price_rub = calculate_postpayment(prepayment)
        item.full_clean()
        item.save(update_fields=(
            "markup_rub", "delivery_rub", "prepayment_price_rub", "postpayment_price_rub"
        ))
    logger.info(
        "Закупочный прайс пересчитан: user_id=%s price_list_id=%s items=%s",
        actor.pk, price_list.pk, len(items),
    )
    return price_list
