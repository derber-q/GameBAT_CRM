from django.core.management.base import BaseCommand

from catalog.system_products import ensure_system_products


class Command(BaseCommand):
    help = "Идемпотентно создаёт две системные позиции и их уникальные штрихкоды."

    def handle(self, *args, **options):
        for product in ensure_system_products():
            self.stdout.write(f"{product.kind}: {product.name} — {product.barcode_entry.value}")
