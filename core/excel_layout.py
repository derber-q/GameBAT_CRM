"""Размеры строк XLSX с учётом шрифта, переноса слов и явных переводов строки."""
from functools import lru_cache
from math import ceil
import os
from pathlib import Path

from PIL import ImageFont


def column_width_pixels(width):
    return int(float(width) * 7 + 5)


@lru_cache(maxsize=32)
def _font(name, size, bold):
    pixels = ceil(size * 96 / 72)
    names = {
        "Arial": "arialbd.ttf" if bold else "arial.ttf",
        "Calibri": "calibrib.ttf" if bold else "calibri.ttf",
    }
    filename = names.get(name, name + ".ttf")
    candidates = (
        str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename),
        filename,
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, pixels)
        except OSError:
            continue
    return ImageFont.load_default(size=pixels)


def text_width_pixels(text, *, font_name="Calibri", font_size=11, bold=False):
    font = _font(font_name, font_size, bold)
    return max((font.getlength(line) for line in str(text or "").splitlines()), default=0)


def wrapped_text_height(text, width, *, font_name="Calibri", font_size=11,
                        bold=False, padding_pixels=12, padding_points=4, min_height=24):
    available = max(1, column_width_pixels(width) - padding_pixels)
    font = _font(font_name, font_size, bold)
    count = 0
    for paragraph in str(text or "").split("\n"):
        remaining = paragraph.rstrip("\r")
        while remaining and font.getlength(remaining) > available:
            low, high = 1, len(remaining)
            while low < high:
                middle = (low + high + 1) // 2
                if font.getlength(remaining[:middle]) <= available:
                    low = middle
                else:
                    high = middle - 1
            space = remaining.rfind(" ", 0, low + 1)
            separators = [remaining.rfind(char, 0, low) + 1 for char in "-/–—"]
            boundary = max([space, *separators])
            cut = boundary if boundary > 0 else low
            remaining = remaining[cut:].lstrip(" ")
            count += 1
        count += 1
    return ceil(max(min_height, count * font_size * 1.3 + padding_points) * 2) / 2
