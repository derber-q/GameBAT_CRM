from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0023_product_stock_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="cd",
            name="exclude_from_supplier_template",
            field=models.BooleanField(
                default=False,
                help_text="Товар не включается в шаблон дисков или техники на странице «Импортные прайсы».",
                verbose_name="Не отображать в шаблоне для поставщиков",
            ),
        ),
        migrations.AddField(
            model_name="tech",
            name="exclude_from_supplier_template",
            field=models.BooleanField(
                default=False,
                help_text="Товар не включается в шаблон дисков или техники на странице «Импортные прайсы».",
                verbose_name="Не отображать в шаблоне для поставщиков",
            ),
        ),
    ]
