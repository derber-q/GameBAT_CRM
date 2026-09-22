from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0002_avitoremotelisting_remote_price"),
    ]

    operations = [
        migrations.AlterField(model_name="avitosyncjob", name="job_type", field=models.CharField(choices=[("product", "Товар"), ("reconcile", "Контрольная сверка"), ("refresh", "Обновление объявлений"), ("manual", "Ручная сверка")], max_length=16, verbose_name="Тип")),
        migrations.AddField(model_name="avitosyncjob", name="total_count", field=models.PositiveIntegerField(default=0, verbose_name="Объявлений к проверке")),
        migrations.AddField(model_name="avitosyncjob", name="checked_count", field=models.PositiveIntegerField(default=0, verbose_name="Проверено")),
        migrations.AddField(model_name="avitosyncjob", name="changed_count", field=models.PositiveIntegerField(default=0, verbose_name="Изменено и подтверждено")),
        migrations.AddField(model_name="avitosyncjob", name="stock_changed_count", field=models.PositiveIntegerField(default=0, verbose_name="Исправлено остатков")),
        migrations.AddField(model_name="avitosyncjob", name="price_changed_count", field=models.PositiveIntegerField(default=0, verbose_name="Исправлено цен")),
        migrations.AddField(model_name="avitosyncjob", name="failed_count", field=models.PositiveIntegerField(default=0, verbose_name="Не удалось синхронизировать")),
        migrations.AddField(model_name="avitosyncjob", name="skipped_count", field=models.PositiveIntegerField(default=0, verbose_name="Неактивных или вне списка")),
        migrations.AddField(model_name="avitosyncjob", name="details", field=models.JSONField(blank=True, default=list, verbose_name="Итог сверки")),
        migrations.AddField(model_name="avitosyncjob", name="phase", field=models.CharField(blank=True, max_length=120, verbose_name="Этап сверки")),
        migrations.AddField(model_name="avitosyncjob", name="current_item", field=models.CharField(blank=True, max_length=255, verbose_name="Текущий товар")),
        migrations.AddField(model_name="avitosyncjob", name="started_at", field=models.DateTimeField(blank=True, null=True, verbose_name="Начало сверки")),
        migrations.AddField(model_name="avitosyncjob", name="finished_at", field=models.DateTimeField(blank=True, null=True, verbose_name="Завершение сверки")),
    ]
