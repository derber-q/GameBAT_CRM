"""Пересборка декоративных WebP из сохранённых оригиналов: python -m resource_storefront.asset_pipeline."""
from pathlib import Path

from PIL import Image


def build():
    root = Path(__file__).resolve().parent.parent / "static" / "resource"
    recipes = (
        ("artwork/gaming-arena.png", (0, 0, 1, 1), "hero-arena.webp", (1000, 1000)),
        ("artwork/gaming-arena.png", (0, 0, 1, 1), "hero-arena-mobile.webp", (640, 640)),
        ("originals/gaming-moodboard.png", (.003, .003, .33, .495), "category-cd.webp", (600, 600)),
        ("artwork/gaming-arena.png", (0, .08, .29, .52), "category-consoles.webp", (500, 600)),
        ("artwork/gaming-arena.png", (0, .50, .30, .72), "category-gamepads.webp", (600, 440)),
        ("originals/premium-gaming-scenes.png", (.26, .59, .496, .94), "category-accessories.webp", (500, 500)),
    )
    for source, bounds, filename, size in recipes:
        with Image.open(root / source) as original:
            image = original.convert("RGB")
        width, height = image.size
        image = image.crop(tuple(round(value * side) for value, side in zip(bounds, (width, height, width, height))))
        image.thumbnail(size)
        image.save(root / "artwork" / filename, "WEBP", quality=88, method=6)
        print(filename)


if __name__ == "__main__":
    build()
