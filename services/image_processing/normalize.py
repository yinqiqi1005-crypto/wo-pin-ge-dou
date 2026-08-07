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
