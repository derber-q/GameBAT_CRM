"""Только чтение API и отчёт сопоставления; не меняет каталог, наценки или деньги."""
import json
from django.core.management.base import BaseCommand, CommandError
from digital_prices.api import CatalogClient, APIError
from digital_prices.models import Integration, Product
from digital_prices.v2_mapping import report
from integrations.crypto import decrypt_secret


class Command(BaseCommand):
    help = 'Прочитать каталог v2 и показать план переноса без применения изменений.'

    def handle(self, *args, **options):
        config = Integration.objects.filter(pk=1, enabled=True).first()
        if config is None or not config.encrypted_key:
            raise CommandError('Интеграция не настроена.')
        client = CatalogClient(decrypt_secret(config.encrypted_key))
        try:
            offers = client.fetch()
        except APIError as exc:
            raise CommandError('Каталог не прочитан: ' + exc.category) from None
        finally:
            client.close()
        self.stdout.write(json.dumps(report(offers, list(Product.objects.all())), ensure_ascii=False, indent=2))
