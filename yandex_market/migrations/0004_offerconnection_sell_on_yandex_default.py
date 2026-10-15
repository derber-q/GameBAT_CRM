from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("yandex_market", "0003_categoryschema_name_categoryschema_placement_rate")]

    operations = [
        migrations.AlterField(
            model_name="offerconnection",
            name="sell_on_yandex",
            field=models.BooleanField(default=True, verbose_name="Продаётся на Яндекс Маркете"),
        ),
    ]
