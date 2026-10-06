"""Кадр каталога вычисляется из оригинала; файл товара никогда не перезаписывается."""
from .models import CatalogImageCrop


def crop_catalog_image(image, product, kind):
    framing = CatalogImageCrop.objects.filter(**{kind: product}, source_image=product.title_image.name).first()
    x, y, zoom = (framing.position_x / 100, framing.position_y / 100, float(framing.zoom)) if framing else (.5, .5, 1)
    width, height = image.size
    crop_width = min(width, height * 3 / 4) / zoom
    crop_height = crop_width * 4 / 3
    left, top = (width - crop_width) * x, (height - crop_height) * y
    return image.crop((round(left), round(top), round(left + crop_width), round(top + crop_height)))
