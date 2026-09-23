from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0003_avitossyncjob_manual_progress")]
    operations = [migrations.AlterField(
        model_name="avitosyncjob", name="job_type",
        field=models.CharField(max_length=16, verbose_name="Тип", choices=[
            ("product", "Товар"), ("reconcile", "Контрольная сверка"),
            ("refresh", "Обновление объявлений"), ("manual", "Ручная сверка"),
            ("status_refresh", "Обновление статусов объявлений"),
        ]),
    )]
