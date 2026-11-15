"""Перевірка фото чека: файл має справді декодуватися як JPG, PNG або WebP (D06)."""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}
MAX_PIXELS = 60_000_000  # захист від «бомб» розпакування
MIN_SIDE_PX = 16


class InvalidImage(ValueError):
    pass


@dataclass(frozen=True)
class ImageInfo:
    content_type: str
    extension: str
    width: int
    height: int


def inspect_image(data: bytes, max_side_px: int) -> ImageInfo:
    """Повністю декодує зображення й повертає його фактичний формат і розміри.

    Заголовку Content-Type від клієнта не довіряємо: формат визначає сам декодер.
    """
    try:
        with Image.open(BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()  # цілісність структури файлу
        with Image.open(BytesIO(data)) as img:
            if img.width * img.height > MAX_PIXELS:
                raise InvalidImage("Зображення має забагато пікселів")
            img.load()  # повне декодування: пошкоджені дані тут дадуть помилку
            width, height = img.size
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as e:
        raise InvalidImage("Файл пошкоджений або не є зображенням") from e

    if fmt not in FORMATS:
        raise InvalidImage("Підтримуються фото у форматах JPG, PNG або WEBP")
    if min(width, height) < MIN_SIDE_PX:
        raise InvalidImage("Зображення занадто маленьке")
    if max(width, height) > max_side_px:
        raise InvalidImage(f"Зображення завелике: щонайбільше {max_side_px} пікселів по стороні")
    content_type, ext = FORMATS[fmt]
    return ImageInfo(content_type=content_type, extension=ext, width=width, height=height)
