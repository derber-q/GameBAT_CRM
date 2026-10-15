from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("yandex_market", "0004_offerconnection_sell_on_yandex_default")]

    operations = [
        migrations.AddField(
            model_name="offerconnection",
            name="resume_display_pending",
            field=models.BooleanField(default=False, verbose_name="Ожидает снятия скрытия после первой привязки"),
        ),
    ]
