from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("yandex_market", "0005_offerconnection_resume_display_pending"),
    ]

    operations = [
        migrations.AlterField(
            model_name="offerconnection",
            name="managed",
            field=models.BooleanField(default=True, verbose_name="Управление подтверждено"),
        ),
        migrations.AlterField(
            model_name="offerconnection",
            name="state",
            field=models.CharField(
                choices=[
                    ("linked", "Ожидает включения управления"),
                    ("queued", "В очереди"),
                    ("syncing", "Синхронизация"),
                    ("synced", "Синхронизирован"),
                    ("error", "Ошибка"),
                    ("attention", "Требуется внимание"),
                ],
                default="queued", max_length=20,
            ),
        ),
    ]
