from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from .exceptions import InvalidImageError

ImageSource = str | Path | BinaryIO

MIN_IMAGE_SIDE = 8


def load_normalized_image(source: ImageSource) -> Image.Image:
    """Read an image, apply EXIF orientation, and return an independent RGBA image."""
    try:
        with Image.open(source) as opened:
            opened.load()
            oriented = ImageOps.exif_transpose(opened)
            normalized = oriented.convert("RGBA").copy()
    except (FileNotFoundError, IsADirectoryError, UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("图片文件损坏或格式不受支持。") from exc

    if min(normalized.size) < MIN_IMAGE_SIDE:
        raise InvalidImageError(f"图片尺寸过小，最短边不能小于 {MIN_IMAGE_SIDE} 像素。")
    return normalized


def crop_square(image: Image.Image) -> Image.Image:
    """Return a centered square crop without resizing the source image in place."""
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def crop_to_ratio(image: Image.Image, *, width: int, height: int) -> Image.Image:
    """Return a centered crop matching the requested grid ratio."""
    source_width, source_height = image.size
    target_ratio = width / height
    source_ratio = source_width / source_height
    if source_ratio > target_ratio:
        cropped_width = round(source_height * target_ratio)
        left = (source_width - cropped_width) // 2
        return image.crop((left, 0, left + cropped_width, source_height))
    cropped_height = round(source_width / target_ratio)
    top = (source_height - cropped_height) // 2
    return image.crop((0, top, source_width, top + cropped_height))
