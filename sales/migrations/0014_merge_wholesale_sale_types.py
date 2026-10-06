from django.db import migrations, models


OLD_WHOLESALE_TYPES = ("wholesale_pickup", "wholesale_delivery")
WHOLESALE = "wholesale"


def merge_wholesale_sale_types(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")
    Sale.objects.using(schema_editor.connection.alias).filter(
        sale_type__in=OLD_WHOLESALE_TYPES,
    ).update(sale_type=WHOLESALE)


def restore_wholesale_pickup_type(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")
    Sale.objects.using(schema_editor.connection.alias).filter(
        sale_type=WHOLESALE,
    ).update(sale_type="wholesale_pickup")


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0013_salecditem_avito_commission_amount_and_more"),
    ]

    operations = [
        migrations.RunPython(
            merge_wholesale_sale_types,
            reverse_code=restore_wholesale_pickup_type,
        ),
        migrations.AlterField(
            model_name="sale",
            name="sale_type",
            field=models.CharField(
                choices=[
                    ("retail", "Розница"),
                    ("wholesale", "Опт"),
                    ("avito", "Авито"),
                    ("yandex_market", "Яндексмаркет"),
                    ("consignment", "Реализация"),
                ],
                max_length=24,
                verbose_name="Тип продажи",
            ),
        ),
    ]
