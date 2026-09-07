from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("catalog", "0002_multiwarehouse_and_pricing"),
        ("partners", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="SupplierCDPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price", models.DecimalField(decimal_places=6, max_digits=20, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Текущая цена")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлена")),
                ("cd", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_prices", to="catalog.cd", verbose_name="CD")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="partners.supplier", verbose_name="Поставщик")),
            ],
            options={
                "verbose_name": "текущая цена поставщика на CD", "verbose_name_plural": "текущие цены поставщиков на CD",
                "permissions": [("view_pricing", "Может просматривать ценообразование"), ("view_supplier_prices", "Может просматривать текущие цены поставщиков"), ("change_supplier_prices", "Может изменять текущие цены поставщиков"), ("change_retail_price", "Может изменять розничные цены"), ("change_wholesale_price", "Может изменять оптовые цены"), ("change_yandex_market_price", "Может изменять цены Яндекс Маркет")],
            },
        ),
        migrations.CreateModel(
            name="SupplierTechPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price", models.DecimalField(decimal_places=6, max_digits=20, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Текущая цена")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлена")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="partners.supplier", verbose_name="Поставщик")),
                ("tech", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_prices", to="catalog.tech", verbose_name="Техника")),
            ],
            options={"verbose_name": "текущая цена поставщика на технику", "verbose_name_plural": "текущие цены поставщиков на технику"},
        ),
        migrations.AddConstraint(model_name="suppliercdprice", constraint=models.UniqueConstraint(fields=("supplier", "cd"), name="unique_supplier_cd_price")),
        migrations.AddConstraint(model_name="suppliercdprice", constraint=models.CheckConstraint(condition=models.Q(("price__gte", 0)), name="supplier_cd_price_nonnegative")),
        migrations.AddConstraint(model_name="suppliertechprice", constraint=models.UniqueConstraint(fields=("supplier", "tech"), name="unique_supplier_tech_price")),
        migrations.AddConstraint(model_name="suppliertechprice", constraint=models.CheckConstraint(condition=models.Q(("price__gte", 0)), name="supplier_tech_price_nonnegative")),
    ]
