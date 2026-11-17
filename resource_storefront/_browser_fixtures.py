"""Искусственные обложки для браузерных проверок без доступа к рабочей базе."""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw


def synthetic_cover(index):
    size = ((300, 420), (500, 300), (320, 320))[index % 3]
    image = Image.new('RGB', size, ('#345878', '#487855', '#784855')[index % 3])
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, size[0]-30, size[1]-30), outline='white', width=8)
    draw.text((45, 45), f'TEST {index}', fill='white')
    stream = BytesIO()
    image.save(stream, format='PNG')
    return ContentFile(stream.getvalue(), name=f'synthetic-cover-{index}.png')
