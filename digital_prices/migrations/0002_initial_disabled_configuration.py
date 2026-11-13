"""Только выключенная конфигурация и номер версии. Импорта или отправок нет."""
from django.db import migrations


def initialize(apps, schema_editor):
    alias = schema_editor.connection.alias
    apps.get_model('digital_prices', 'CatalogState').objects.using(alias).get_or_create(pk=1)
    apps.get_model('digital_prices', 'Integration').objects.using(alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('digital_prices', '0001_digital_price_catalog')]
    operations = [migrations.RunPython(initialize, migrations.RunPython.noop)]
