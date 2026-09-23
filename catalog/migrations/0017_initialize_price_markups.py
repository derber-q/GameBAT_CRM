from decimal import Decimal
from django.db import migrations


def initialize_markups(apps, schema_editor):
    for name in ("CD", "Tech"):
        apps.get_model("catalog", name).objects.using(schema_editor.connection.alias).update(
            avito_markup_from_wholesale=Decimal("200.00"),
            yandex_markup_from_wholesale=Decimal("200.00"),
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0016_price_markup_fields")]
    operations = [migrations.RunPython(initialize_markups, migrations.RunPython.noop)]
