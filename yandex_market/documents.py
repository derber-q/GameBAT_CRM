"""Официальные PDF Маркета и отдельные публичные изображения товаров."""
import ipaddress
import socket
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q

from .client import MarketError, NoRedirect
from .content import public_https
from .models import LabelDocument, Media, OrderMetadata


@transaction.atomic
def request_labels(*, integration, orders, actor, format_name='A7', box_id=None, shipment_id=None, reuse=False):
    """Официальный PDF получает worker; повторный запрос из продажи использует тот же документ."""
    from django.core.exceptions import PermissionDenied
    from .queue import enqueue
    from .services import audit

    if not actor.has_perm('yandex_market.print_labels'):
        raise PermissionDenied
    if format_name not in {'A7', 'A4', 'A9', 'A9_HORIZONTALLY'}:
        raise ValidationError('Неизвестный формат ярлыка.')
    if not orders or len(orders) > 1000 or any(o.integration_id != integration.pk for o in orders):
        raise ValidationError('Выберите от 1 до 1000 заказов одного магазина.')
    values = {'integration': integration, 'format': format_name, 'created_by': actor}
    if len(orders) == 1:
        order = OrderMetadata.objects.select_for_update().get(pk=orders[0].pk)
        values['order'] = order
        if box_id or shipment_id:
            if not box_id or not shipment_id or not str(box_id).isdecimal() or not str(shipment_id).isdecimal():
                raise ValidationError('Укажите идентификаторы коробки и отправления.')
            values.update(box_id=int(box_id), shipment_id=int(shipment_id))
        if reuse:
            document = order.labels.filter(format=format_name, box_id=values.get('box_id'),
                shipment_id=values.get('shipment_id')).filter(
                    Q(state__in=['pending', 'processing']) | (Q(state='done') & ~Q(file=''))
                ).order_by('-pk').first()
            if document:
                return document
    else:
        values['order_ids'] = [o.order_id for o in orders]
    document = LabelDocument.objects.create(**values)
    # Документ и DB-задание фиксируются вместе; worker увидит оба только после commit.
    enqueue(integration, 'label', document.pk, {'document_id': document.pk}, actor=actor)
    audit(integration, actor, 'labels_requested', document.pk, orders=[o.order_id for o in orders])
    return document


def download_public(url, *, pdf=False):
    public_https(url)
    parsed = urlparse(url)
    host = parsed.hostname
    if pdf and not any(host == suffix or host.endswith("." + suffix) for suffix in ("yandex.ru", "yandex.net", "yandexcloud.net", "yandex.com")):
        raise ValidationError("API вернул неизвестный адрес официального отчёта.")
    addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValidationError("Ссылка ведёт в закрытую сеть.")
    try:
        with build_opener(NoRedirect()).open(Request(url, headers={"Accept": "application/pdf" if pdf else "image/*"}), timeout=20) as response:
            data = response.read(30 * 1024 * 1024 + 1)
    except OSError:
        raise MarketError("Не удалось скачать файл по публичной ссылке.", "DOWNLOAD", retryable=True) from None
    if len(data) > 30 * 1024 * 1024 or (pdf and not data.startswith(b"%PDF-")):
        raise ValidationError("Файл имеет неверный формат или слишком велик.")
    return data


def save_image(connection, upload, *, position=None):
    try:
        if getattr(upload, "size", 0) > 20 * 1024 * 1024:
            raise ValueError()
        image = Image.open(upload)
        if image.width * image.height > 40_000_000:
            raise ValueError()
        image.load()
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=95)
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError("Загрузите изображение JPG/PNG/WebP до 20 МБ и 40 мегапикселей.") from None
    media = Media(connection=connection, position=position if position is not None else connection.media.count())
    media.image.save("product.jpg", ContentFile(output.getvalue()), save=True)
    return media


def process_label(document_id, client):
    document = LabelDocument.objects.select_related("order").get(pk=document_id)
    if document.state == "done" and document.file:
        return
    if document.order_id:
        params = {"orderId": document.order.order_id}
        operation = "generateOrderLabels"
        if document.box_id:
            operation = "generateOrderLabel"
            params.update(shipmentId=document.shipment_id, boxId=document.box_id)
        data = client.call(operation, params=params, query={"format": document.format}, pdf=True, entity_id=document.order.order_id)
    else:
        if not document.report_id:
            response = client.call("generateMassOrderLabelsReport", body={"businessId": document.integration.business_id, "orderIds": document.order_ids}, query={"format": document.format})
            document.report_id = response["result"]["reportId"]
            document.state = "processing"
            document.save(update_fields=["report_id", "state"])
        info = client.call("getReportInfo", params={"reportId": document.report_id})["result"]
        if info["status"] in {"PENDING", "PROCESSING"}:
            raise MarketError("Маркет готовит PDF. Проверка продолжится автоматически.", "REPORT_PENDING", retryable=True, retry_after=10)
        if info["status"] != "DONE" or info.get("subStatus"):
            raise ValidationError("Маркет не сформировал полный комплект ярлыков: " + str(info.get("subStatus", info["status"])))
        data = download_public(info["file"], pdf=True)
    document.file.save(f"labels-{document.pk}.pdf", ContentFile(data), save=False)
    document.state = "done"
    document.last_error = ""
    document.save(update_fields=["file", "state", "last_error"])
