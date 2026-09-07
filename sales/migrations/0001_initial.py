from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import sales.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("catalog", "0002_multiwarehouse_and_pricing"),
        ("warehouse", "0003_transfers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Sale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("visible_id", models.CharField(default=sales.models.temporary_sale_id, editable=False, max_length=40, unique=True, verbose_name="Номер продажи")),
                ("price_type", models.CharField(choices=[("retail", "Розничная"), ("wholesale", "Оптовая"), ("yandex_market", "Яндекс Маркет")], max_length=24, verbose_name="Тип цены")),
                ("sale_type", models.CharField(choices=[("retail", "Розница"), ("wholesale_pickup", "Опт самовывоз"), ("wholesale_delivery", "Опт доставка"), ("avito", "Авито"), ("yandex_market", "Яндексмаркет")], max_length=24, verbose_name="Тип продажи")),
                ("payment_method", models.CharField(choices=[("cash", "Наличные"), ("cash_postpay", "Наличные — постоплата"), ("bank_account", "Банковский счёт")], max_length=24, verbose_name="Способ оплаты")),
                ("order_status", models.CharField(choices=[("created", "Создан"), ("assembled", "Собран"), ("shipped", "Отправлен"), ("delivered", "Доставлен")], default="created", editable=False, max_length=20, verbose_name="Статус заказа")),
                ("payment_status", models.CharField(choices=[("unpaid", "Не оплачен"), ("paid", "Оплачен")], default="unpaid", editable=False, max_length=20, verbose_name="Статус оплаты")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлена")),
                ("completed_at", models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Завершена")),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=20, verbose_name="Сумма")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_sales", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales", to="warehouse.warehouse", verbose_name="Склад")),
            ],
            options={
                "verbose_name": "продажа", "verbose_name_plural": "продажи", "ordering": ("-created_at", "-id"),
                "permissions": [("view_sales", "Может просматривать незавершённые продажи"), ("view_completed_sales", "Может просматривать завершённые продажи"), ("view_sale_detail", "Может просматривать подробности продажи"), ("create_sale", "Может создавать продажи"), ("edit_unpaid_postpay_sale", "Может изменять неоплаченную продажу с постоплатой"), ("advance_order_status", "Может менять статус заказа"), ("mark_sale_paid", "Может подтверждать оплату продажи")],
            },
        ),
        migrations.CreateModel(
            name="SaleCDItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(verbose_name="Количество")),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=20, verbose_name="Цена единицы")),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=20, verbose_name="Сумма строки")),
                ("product_name_snapshot", models.CharField(max_length=255, verbose_name="Название товара")),
                ("article_snapshot", models.CharField(max_length=100, verbose_name="Артикул")),
                ("cd", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sale_items", to="catalog.cd", verbose_name="CD")),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cd_items", to="sales.sale", verbose_name="Продажа")),
            ],
            options={"verbose_name": "позиция CD в продаже", "verbose_name_plural": "позиции CD в продажах"},
        ),
        migrations.CreateModel(
            name="SaleTechItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(verbose_name="Количество")),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=20, verbose_name="Цена единицы")),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=20, verbose_name="Сумма строки")),
                ("product_name_snapshot", models.CharField(max_length=255, verbose_name="Название товара")),
                ("article_snapshot", models.CharField(max_length=100, verbose_name="Артикул")),
                ("sale", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tech_items", to="sales.sale", verbose_name="Продажа")),
                ("tech", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sale_items", to="catalog.tech", verbose_name="Техника")),
            ],
            options={"verbose_name": "позиция техники в продаже", "verbose_name_plural": "позиции техники в продажах"},
        ),
        migrations.AddConstraint(model_name="sale", constraint=models.CheckConstraint(condition=models.Q(("total_amount__gte", 0)), name="sale_total_nonnegative")),
        migrations.AddConstraint(model_name="salecditem", constraint=models.UniqueConstraint(fields=("sale", "cd"), name="unique_sale_cd_item")),
        migrations.AddConstraint(model_name="salecditem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="sale_cd_quantity_positive")),
        migrations.AddConstraint(model_name="salecditem", constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="sale_cd_price_nonnegative")),
        migrations.AddConstraint(model_name="salecditem", constraint=models.CheckConstraint(condition=models.Q(("line_total__gte", 0)), name="sale_cd_total_nonnegative")),
        migrations.AddConstraint(model_name="saletechitem", constraint=models.UniqueConstraint(fields=("sale", "tech"), name="unique_sale_tech_item")),
        migrations.AddConstraint(model_name="saletechitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="sale_tech_quantity_positive")),
        migrations.AddConstraint(model_name="saletechitem", constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="sale_tech_price_nonnegative")),
        migrations.AddConstraint(model_name="saletechitem", constraint=models.CheckConstraint(condition=models.Q(("line_total__gte", 0)), name="sale_tech_total_nonnegative")),
    ]
