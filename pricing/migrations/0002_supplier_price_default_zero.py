from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("pricing", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="suppliercdprice",
            name="price",
            field=models.DecimalField(
                decimal_places=6,
                default=0,
                max_digits=20,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Текущая цена",
            ),
        ),
        migrations.AlterField(
            model_name="suppliertechprice",
            name="price",
            field=models.DecimalField(
                decimal_places=6,
                default=0,
                max_digits=20,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Текущая цена",
            ),
        ),
    ]
