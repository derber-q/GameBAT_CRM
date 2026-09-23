from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0015_multiple_product_barcodes")]
    operations = []
    for model in ("cd", "tech"):
        for channel, label in (("avito", "Avito"), ("yandex", "Яндекс Маркет")):
            name = f"{channel}_markup_from_wholesale"
            operations.append(migrations.AddField(
                model_name=model, name=name,
                field=models.DecimalField(
                    verbose_name=f"Наценка от опта для {label}", max_digits=20, decimal_places=2,
                    default=Decimal("200.00"), null=True, blank=True, validators=[MinValueValidator(0)],
                ),
            ))
            operations.append(migrations.AddConstraint(
                model_name=model,
                constraint=models.CheckConstraint(
                    condition=models.Q(**{f"{name}__gte": 0}) | models.Q(**{f"{name}__isnull": True}),
                    name=f"{model}_{channel}_markup_nonnegative",
                ),
            ))
