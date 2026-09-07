from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("warehouse", "0002_migrate_legacy_stock"),
    ]
    operations = [
        migrations.RemoveConstraint(model_name="cd", name="cd_quantity_nonnegative"),
        migrations.RemoveConstraint(model_name="tech", name="tech_quantity_nonnegative"),
        migrations.RemoveField(model_name="cd", name="quantity"),
        migrations.RemoveField(model_name="tech", name="quantity"),
        migrations.AddField(model_name="cd", name="retail_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Розничная цена")),
        migrations.AddField(model_name="cd", name="wholesale_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Оптовая цена")),
        migrations.AddField(model_name="cd", name="yandex_market_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Цена Яндекс Маркет")),
        migrations.AddField(model_name="tech", name="retail_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Розничная цена")),
        migrations.AddField(model_name="tech", name="wholesale_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Оптовая цена")),
        migrations.AddField(model_name="tech", name="yandex_market_price", field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Цена Яндекс Маркет")),
        migrations.AddConstraint(model_name="cd", constraint=models.CheckConstraint(condition=models.Q(("retail_price__gte", 0), ("retail_price__isnull", True), _connector="OR"), name="cd_retail_price_nonnegative")),
        migrations.AddConstraint(model_name="cd", constraint=models.CheckConstraint(condition=models.Q(("wholesale_price__gte", 0), ("wholesale_price__isnull", True), _connector="OR"), name="cd_wholesale_price_nonnegative")),
        migrations.AddConstraint(model_name="cd", constraint=models.CheckConstraint(condition=models.Q(("yandex_market_price__gte", 0), ("yandex_market_price__isnull", True), _connector="OR"), name="cd_yandex_price_nonnegative")),
        migrations.AddConstraint(model_name="tech", constraint=models.CheckConstraint(condition=models.Q(("retail_price__gte", 0), ("retail_price__isnull", True), _connector="OR"), name="tech_retail_price_nonnegative")),
        migrations.AddConstraint(model_name="tech", constraint=models.CheckConstraint(condition=models.Q(("wholesale_price__gte", 0), ("wholesale_price__isnull", True), _connector="OR"), name="tech_wholesale_price_nonnegative")),
        migrations.AddConstraint(model_name="tech", constraint=models.CheckConstraint(condition=models.Q(("yandex_market_price__gte", 0), ("yandex_market_price__isnull", True), _connector="OR"), name="tech_yandex_price_nonnegative")),
    ]
