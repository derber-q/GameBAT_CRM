from django.db import migrations, models
import django.db.models.deletion


def populate_barcode_registry(apps, schema_editor):
    CD = apps.get_model("catalog", "CD")
    Tech = apps.get_model("catalog", "Tech")
    Registry = apps.get_model("catalog", "BarcodeRegistry")
    seen = {}
    registrations = []
    for product_kind, model, field_name in (("cd", CD, "cd"), ("tech", Tech, "tech")):
        for product in model.objects.exclude(barcode="").order_by("pk"):
            value = str(product.barcode or "").strip()
            if not value:
                continue
            if value in seen:
                previous_kind, previous_id = seen[value]
                raise RuntimeError(
                    "Конфликт штрихкода %s: %s #%s и %s #%s. "
                    "Исправьте данные до миграции."
                    % (value, previous_kind, previous_id, product_kind, product.pk)
                )
            seen[value] = (product_kind, product.pk)
            registrations.append(Registry(
                value=value,
                product_kind=product_kind,
                **{field_name: product},
            ))
    Registry.objects.bulk_create(registrations)


def clear_barcode_registry(apps, schema_editor):
    apps.get_model("catalog", "BarcodeRegistry").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0008_product_weights_and_optional_sku")]

    operations = [
        migrations.CreateModel(
            name="BarcodeRegistry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.CharField(max_length=100, unique=True, verbose_name="Штрихкод")),
                ("product_kind", models.CharField(choices=[("cd", "CD"), ("tech", "Tech")], max_length=8, verbose_name="Тип товара")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("cd", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="barcode_registration", to="catalog.cd", verbose_name="CD")),
                ("tech", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="barcode_registration", to="catalog.tech", verbose_name="Tech")),
            ],
            options={
                "verbose_name": "регистрация штрихкода",
                "verbose_name_plural": "реестр штрихкодов",
                "ordering": ("value",),
            },
        ),
        migrations.AddConstraint(
            model_name="barcoderegistry",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="barcode_registry_exact_product",
            ),
        ),
        migrations.RunPython(populate_barcode_registry, clear_barcode_registry),
    ]
