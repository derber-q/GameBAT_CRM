from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


def set_markups(apps, schema_editor):
    for name in ("CD", "Tech"):
        apps.get_model("catalog", name).objects.using(schema_editor.connection.alias).all().update(
            avito_markup_from_wholesale=Decimal("189.00"),
            yandex_markup_from_wholesale=Decimal("189.00"),
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0017_initialize_price_markups")]
    operations = [
        migrations.AlterField(
            model_name=model, name=f"{channel}_markup_from_wholesale",
            field=models.DecimalField(
                "Наценка от опта для Avito" if channel == "avito" else "Наценка от опта для Яндекс Маркет",
                max_digits=20, decimal_places=2, default=Decimal("189.00"),
                null=True, blank=True, validators=[MinValueValidator(0)],
            ),
        )
        for model in ("cd", "tech") for channel in ("avito", "yandex")
    ] + [migrations.RunPython(set_markups, migrations.RunPython.noop)]
