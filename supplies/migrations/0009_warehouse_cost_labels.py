from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("supplies", "0008_alter_supply_options_supplyfinalization_and_more")]

    operations = [
        migrations.AlterField(
            model_name="supplycostcalculation",
            name="old_owned_quantity",
            field=models.PositiveIntegerField(
                "Количество на физических складах до поставки", editable=False
            ),
        ),
        migrations.AlterField(
            model_name="supplyfinalizationitem",
            name="global_quantity_snapshot",
            field=models.PositiveIntegerField(
                "Остаток на физических складах", editable=False
            ),
        ),
    ]
