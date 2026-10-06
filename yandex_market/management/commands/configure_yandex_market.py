"""Первичная настройка отключённого подключения; только чтение внешнего API."""
from pathlib import Path
import os
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from integrations.crypto import encrypt_secret
from warehouse.models import Warehouse
from yandex_market.client import MarketError
from yandex_market.models import Integration
from yandex_market.services import check_connection, refresh_catalog


class Command(BaseCommand):
    help = "Сохранить ключ в зашифрованный файл и проверить отключённое FBS-подключение (без внешних изменений)."

    def add_arguments(self, parser):
        parser.add_argument("--key-file")
        parser.add_argument("--business", type=int, required=True)
        parser.add_argument("--campaign", type=int, required=True)
        parser.add_argument("--partner-warehouse", type=int, required=True)
        parser.add_argument("--warehouse", type=int, required=True)
        parser.add_argument("--operator", type=int, required=True)
        parser.add_argument("--name", default="Яндекс Маркет FBS")
        parser.add_argument("--read-catalog", action="store_true")

    def handle(self, *args, **options):
        warehouse = Warehouse.objects.get(pk=options["warehouse"])
        operator = get_user_model().objects.get(pk=options["operator"], is_active=True)
        if options["key_file"]:
            source = Path(options["key_file"])
            value = source.read_text("utf-8-sig").strip()
            if not value or any(char.isspace() for char in value):
                raise CommandError("В файле должен находиться только API-Key без пробелов.")
            target = Path(settings.YANDEX_MARKET_KEY_FILE)
            descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".ym-key-")
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(encrypt_secret(value))
                os.chmod(temporary, 0o600)
                os.replace(temporary, target)
            finally:
                if Path(temporary).exists():
                    Path(temporary).unlink()
        integration, created = Integration.objects.get_or_create(business_id=options["business"], defaults={
            "campaign_id": options["campaign"], "partner_warehouse_id": options["partner_warehouse"],
            "fulfillment_warehouse": warehouse, "operator": operator, "name": options["name"], "enabled": False,
        })
        if integration.campaign_id != options["campaign"] or integration.partner_warehouse_id != options["partner_warehouse"]:
            raise CommandError("Существующее подключение имеет другие идентификаторы. Исправьте настройки в интерфейсе.")
        try:
            check_connection(integration)
            if options["read_catalog"]:
                count = refresh_catalog(integration)
                self.stdout.write(f"Получено товаров: {count}. Связи и номенклатура автоматически не создавались.")
        except (ValidationError, MarketError) as exc:
            raise CommandError(" ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)) from None
        self.stdout.write(self.style.SUCCESS(f"Подключение #{integration.pk} проверено. Фоновый обмен: {'включён' if integration.enabled else 'выключен'}."))
