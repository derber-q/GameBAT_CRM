from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_barcodes(apps, schema_editor):
    CD = apps.get_model("catalog", "CD")
    Tech = apps.get_model("catalog", "Tech")
    Barcode = apps.get_model("catalog", "BarcodeRegistry")

    legacy = []
    owners = {}
    conflicts = []
    for kind, model in (("cd", CD), ("tech", Tech)):
        for product in model.objects.exclude(barcode="").order_by("pk"):
            value = str(product.barcode or "").strip()
            if not value:
                continue
            owner = (kind, product.pk)
            if value in owners and owners[value] != owner:
                conflicts.append((value, owners[value], owner))
            owners[value] = owner
            legacy.append((kind, product.pk, value))
    if conflicts:
        details = "; ".join(
            f"{value}: {first[0]}#{first[1]} / {second[0]}#{second[1]}"
            for value, first, second in conflicts[:20]
        )
        raise RuntimeError(f"Конфликты старых штрихкодов; миграция остановлена: {details}")

    for kind, product_id, value in legacy:
        current = Barcode.objects.filter(value=value).first()
        if current:
            current_owner = ("cd", current.cd_id) if current.cd_id else ("tech", current.tech_id)
            if current_owner != (kind, product_id):
                raise RuntimeError(
                    f"Штрихкод {value} уже связан с {current_owner[0]}#{current_owner[1]}, "
                    f"ожидался {kind}#{product_id}."
                )
            continue
        Barcode.objects.create(
            value=value,
            product_kind=kind,
            cd_id=product_id if kind == "cd" else None,
            tech_id=product_id if kind == "tech" else None,
        )

    missing = [
        (kind, product_id, value)
        for kind, product_id, value in legacy
        if not Barcode.objects.filter(
            value=value,
            **({"cd_id": product_id, "tech_id": None} if kind == "cd" else {"tech_id": product_id, "cd_id": None}),
        ).exists()
    ]
    invalid = Barcode.objects.filter(cd_id__isnull=True, tech_id__isnull=True).exists() or Barcode.objects.filter(
        cd_id__isnull=False, tech_id__isnull=False
    ).exists()
    if missing or invalid:
        raise RuntimeError("Проверка целостности миграции штрихкодов не пройдена.")


def restore_legacy_barcodes(apps, schema_editor):
    CD = apps.get_model("catalog", "CD")
    Tech = apps.get_model("catalog", "Tech")
    Barcode = apps.get_model("catalog", "BarcodeRegistry")
    for kind, model, owner_field in (("cd", CD, "cd_id"), ("tech", Tech, "tech_id")):
        for product in model.objects.all().order_by("pk"):
            value = Barcode.objects.filter(**{owner_field: product.pk}).order_by("id").values_list(
                "value", flat=True
            ).first() or ""
            model.objects.filter(pk=product.pk).update(barcode=value)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0014_cd_archived_at_cd_archived_by_cd_is_archived_and_more")]

    operations = [
        migrations.AlterField(
            model_name="barcoderegistry",
            name="cd",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="barcodes", to="catalog.cd", verbose_name="CD",
            ),
        ),
        migrations.AlterField(
            model_name="barcoderegistry",
            name="tech",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="barcodes", to="catalog.tech", verbose_name="Tech",
            ),
        ),
        migrations.RunPython(migrate_legacy_barcodes, restore_legacy_barcodes),
        migrations.RemoveField(model_name="cd", name="barcode"),
        migrations.RemoveField(model_name="tech", name="barcode"),
    ]
