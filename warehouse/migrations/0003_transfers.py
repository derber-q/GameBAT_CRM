from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("warehouse", "0002_migrate_legacy_stock"),
        ("catalog", "0002_multiwarehouse_and_pricing"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="WarehouseTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("created", "Создан"), ("assembled", "Собран"), ("shipped", "Отправлен"), ("accepted", "Принят")], default="created", editable=False, max_length=20, verbose_name="Статус")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                ("assembled_at", models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Собран")),
                ("shipped_at", models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Отправлен")),
                ("accepted_at", models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Принят")),
                ("accepted_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accepted_warehouse_transfers", to=settings.AUTH_USER_MODEL, verbose_name="Принял")),
                ("assembled_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="assembled_warehouse_transfers", to=settings.AUTH_USER_MODEL, verbose_name="Собрал")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_warehouse_transfers", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("destination_warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transfers", to="warehouse.warehouse", verbose_name="Склад-получатель")),
                ("shipped_by", models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="shipped_warehouse_transfers", to=settings.AUTH_USER_MODEL, verbose_name="Отправил")),
                ("source_warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transfers", to="warehouse.warehouse", verbose_name="Склад-отправитель")),
            ],
            options={
                "verbose_name": "межскладское перемещение", "verbose_name_plural": "межскладские перемещения",
                "ordering": ("-created_at", "-id"),
                "permissions": [("view_transfers", "Может просматривать перемещения"), ("create_transfer", "Может создавать перемещения"), ("mark_transfer_assembled", "Может отмечать перемещение собранным"), ("mark_transfer_shipped", "Может отмечать перемещение отправленным"), ("mark_transfer_accepted", "Может принимать перемещение")],
            },
        ),
        migrations.CreateModel(
            name="CDWarehouseTransferItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(verbose_name="Количество")),
                ("cd", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_transfer_items", to="catalog.cd", verbose_name="CD")),
                ("transfer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cd_items", to="warehouse.warehousetransfer", verbose_name="Перемещение")),
            ],
            options={"verbose_name": "позиция CD в перемещении", "verbose_name_plural": "позиции CD в перемещениях"},
        ),
        migrations.CreateModel(
            name="TechWarehouseTransferItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(verbose_name="Количество")),
                ("tech", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_transfer_items", to="catalog.tech", verbose_name="Техника")),
                ("transfer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tech_items", to="warehouse.warehousetransfer", verbose_name="Перемещение")),
            ],
            options={"verbose_name": "позиция техники в перемещении", "verbose_name_plural": "позиции техники в перемещениях"},
        ),
        migrations.AddConstraint(model_name="warehousetransfer", constraint=models.CheckConstraint(condition=models.Q(("source_warehouse", models.F("destination_warehouse")), _negated=True), name="warehouse_transfer_different_destinations")),
        migrations.AddConstraint(model_name="cdwarehousetransferitem", constraint=models.UniqueConstraint(fields=("transfer", "cd"), name="unique_cd_transfer_item")),
        migrations.AddConstraint(model_name="cdwarehousetransferitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="cd_transfer_quantity_positive")),
        migrations.AddConstraint(model_name="techwarehousetransferitem", constraint=models.UniqueConstraint(fields=("transfer", "tech"), name="unique_tech_transfer_item")),
        migrations.AddConstraint(model_name="techwarehousetransferitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="tech_transfer_quantity_positive")),
    ]
