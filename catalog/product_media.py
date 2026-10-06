"""Проверка и атомарное управление изображениями номенклатуры."""
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .audit import field_change, record_product_changes
from .models import CD, ProductChangeEvent, ProductImage, Tech


MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_GALLERY_UPLOADS = 30
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def product_model(product_kind):
    if product_kind == "cd":
        return CD
    if product_kind == "tech":
        return Tech
    raise ValidationError("Неизвестный тип товара.")


def validate_product_image(upload):
    """Проверяет реальное содержимое изображения, а не только расширение файла."""
    if upload is None:
        raise ValidationError("Выберите изображение.")
    if upload.size > MAX_IMAGE_BYTES:
        raise ValidationError("Размер изображения не должен превышать 20 МБ.")
    content_type = getattr(upload, "content_type", "")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Допустимы изображения JPG, PNG и WebP.")
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            if image.format not in ALLOWED_FORMATS:
                raise ValidationError("Допустимы изображения JPG, PNG и WebP.")
            image_format = image.format
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValidationError("Изображение не должно превышать 40 мегапикселей.")
            image.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("Файл не является корректным изображением JPG, PNG или WebP.") from None
    finally:
        upload.seek(0)
    upload.name = f"{Path(upload.name).stem}{FORMAT_EXTENSIONS[image_format]}"
    return upload


def _delete_file(storage, name):
    if name:
        storage.delete(name)


def set_title_image(*, actor, product_kind, product_id, upload):
    validate_product_image(upload)
    model = product_model(product_kind)
    saved_name = ""
    storage = None
    try:
        with transaction.atomic():
            product = model.objects.select_for_update().get(pk=product_id)
            if product.is_archived:
                raise ValidationError("Удалённый товар нельзя изменять.")
            old_name = product.title_image.name
            old_storage = product.title_image.storage
            product.title_image.save(Path(upload.name).name, upload, save=False)
            storage = product.title_image.storage
            saved_name = product.title_image.name
            product.save(update_fields=("title_image",))
            record_product_changes(
                actor=actor,
                instance=product,
                changes=[field_change(
                    field_name="title_image",
                    field_label="Титульное фото",
                    old_value=Path(old_name).name if old_name else "",
                    new_value=Path(saved_name).name,
                )],
                source=ProductChangeEvent.Source.NOMENCLATURE,
            )
            if old_name and old_name != saved_name:
                transaction.on_commit(lambda: _delete_file(old_storage, old_name))
            return product
    except Exception:
        if storage is not None and saved_name:
            storage.delete(saved_name)
        raise


def delete_title_image(*, actor, product_kind, product_id):
    model = product_model(product_kind)
    with transaction.atomic():
        product = model.objects.select_for_update().get(pk=product_id)
        if product.is_archived:
            raise ValidationError("Удалённый товар нельзя изменять.")
        old_name = product.title_image.name
        if not old_name:
            return product
        storage = product.title_image.storage
        product.title_image = ""
        product.save(update_fields=("title_image",))
        record_product_changes(
            actor=actor,
            instance=product,
            changes=[field_change(
                field_name="title_image",
                field_label="Титульное фото",
                old_value=Path(old_name).name,
                new_value="",
            )],
            source=ProductChangeEvent.Source.NOMENCLATURE,
        )
        transaction.on_commit(lambda: _delete_file(storage, old_name))
        return product


def add_gallery_images(*, actor, product_kind, product_id, image_kind, uploads):
    if image_kind not in ProductImage.ImageKind.values:
        raise ValidationError("Неизвестная категория изображений.")
    uploads = list(uploads)
    if not uploads:
        raise ValidationError("Выберите хотя бы одно изображение.")
    if len(uploads) > MAX_GALLERY_UPLOADS:
        raise ValidationError("За один раз можно загрузить не более 30 изображений.")
    for upload in uploads:
        validate_product_image(upload)

    model = product_model(product_kind)
    created_files = []
    try:
        with transaction.atomic():
            product = model.objects.select_for_update().get(pk=product_id)
            if product.is_archived:
                raise ValidationError("Удалённый товар нельзя изменять.")
            relation = {"cd": product} if product_kind == "cd" else {"tech": product}
            last_order = ProductImage.objects.filter(
                product_kind=product_kind,
                image_kind=image_kind,
                **relation,
            ).aggregate(value=Max("sort_order"))["value"]
            next_order = (last_order if last_order is not None else -1) + 1
            created = []
            for offset, upload in enumerate(uploads):
                item = ProductImage(
                    product_kind=product_kind,
                    image_kind=image_kind,
                    sort_order=next_order + offset,
                    **relation,
                )
                item.image.save(Path(upload.name).name, upload, save=False)
                created_files.append((item.image.storage, item.image.name))
                item.save()
                created.append(item)
            label = dict(ProductImage.ImageKind.choices)[image_kind]
            record_product_changes(
                actor=actor,
                instance=product,
                changes=[field_change(
                    field_name=f"{image_kind}_images_added",
                    field_label=f"{label}: добавлено",
                    old_value="0",
                    new_value=len(created),
                )],
                source=ProductChangeEvent.Source.NOMENCLATURE,
            )
            return created
    except Exception:
        for storage, name in created_files:
            storage.delete(name)
        raise


def delete_gallery_image(*, actor, product_kind, product_id, image_id):
    model = product_model(product_kind)
    relation_filter = {"cd_id": product_id} if product_kind == "cd" else {"tech_id": product_id}
    with transaction.atomic():
        product = model.objects.select_for_update().get(pk=product_id)
        if product.is_archived:
            raise ValidationError("Удалённый товар нельзя изменять.")
        item = ProductImage.objects.select_for_update().get(
            pk=image_id,
            product_kind=product_kind,
            **relation_filter,
        )
        storage = item.image.storage
        name = item.image.name
        label = item.get_image_kind_display()
        item.delete()
        record_product_changes(
            actor=actor,
            instance=product,
            changes=[field_change(
                field_name=f"{item.image_kind}_image_deleted",
                field_label=f"{label}: удалено",
                old_value=Path(name).name,
                new_value="",
            )],
            source=ProductChangeEvent.Source.NOMENCLATURE,
        )
        transaction.on_commit(lambda: _delete_file(storage, name))
        return product
