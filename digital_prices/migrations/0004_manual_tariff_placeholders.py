"""Пустые ручные строки по образцу владельца. Цены с изображений не переносятся."""
from django.db import migrations


def populate(apps, schema_editor):
    Entry = apps.get_model('digital_prices', 'ManualPriceEntry')
    alias = schema_editor.connection.alias
    groups = {
        'turkey': ('coefficient', ['1–99', '100–249', '250–499', '500–999', '1000–1999', '2000–2999', '3000–3999', '4000+']),
        'sng': ('coefficient', ['1–99', '100–349', '350–999', '1000–1999', '2000–2999', '3000–3999', '4000+']),
        'india': ('rub', ['1000', '2000', '3000', '4000', '5000', '6000']),
        'poland': ('rub', ['50', '100', '200', '650', '900', '1100']),
        'indonesia': ('rub', ['100K', '225K', '300K', '600K', '1M', '1.5M']),
        'usa': ('rub', ['5', '10', '25', '50', '75', '100']),
    }
    for region, (unit, labels) in groups.items():
        for position, label in enumerate(labels):
            Entry.objects.using(alias).get_or_create(kind='game_tariff', region=region, label=label,
                defaults={'unit': unit, 'position': position})
    for position, label in enumerate(['До 99 ₽', '100–499 ₽', '500–999 ₽', 'От 1000 ₽']):
        Entry.objects.using(alias).get_or_create(kind='steam_tariff', region='', label=label,
            defaults={'unit': 'percent', 'position': position})


class Migration(migrations.Migration):
    dependencies = [('digital_prices', '0003_manual_price_entries')]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]
