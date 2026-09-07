from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True, verbose_name="Название")),
            ],
            options={
                "verbose_name": "склад",
                "verbose_name_plural": "склады",
                "ordering": ("name",),
                "permissions": [
                    ("view_global_stock", "Может просматривать общие остатки"),
                    ("view_warehouse_stock", "Может просматривать остатки отдельного склада"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CDWarehouseStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0, verbose_name="Количество")),
                ("cd", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_stocks", to="catalog.cd", verbose_name="CD")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cd_stocks", to="warehouse.warehouse", verbose_name="Склад")),
            ],
            options={"verbose_name": "остаток CD на складе", "verbose_name_plural": "остатки CD на складах"},
        ),
        migrations.CreateModel(
            name="TechWarehouseStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0, verbose_name="Количество")),
                ("tech", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_stocks", to="catalog.tech", verbose_name="Техника")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tech_stocks", to="warehouse.warehouse", verbose_name="Склад")),
            ],
            options={"verbose_name": "остаток техники на складе", "verbose_name_plural": "остатки техники на складах"},
        ),
        migrations.AddConstraint(
            model_name="cdwarehousestock",
            constraint=models.UniqueConstraint(fields=("warehouse", "cd"), name="unique_cd_warehouse_stock"),
        ),
        migrations.AddConstraint(
            model_name="cdwarehousestock",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gte", 0)), name="cd_warehouse_quantity_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="techwarehousestock",
            constraint=models.UniqueConstraint(fields=("warehouse", "tech"), name="unique_tech_warehouse_stock"),
        ),
        migrations.AddConstraint(
            model_name="techwarehousestock",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gte", 0)), name="tech_warehouse_quantity_nonnegative"),
        ),
    ]
