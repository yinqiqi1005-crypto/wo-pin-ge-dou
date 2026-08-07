from io import BytesIO

import pytest
from PIL import Image

from services.image_processing import InvalidImageError
from services.image_processing.normalize import crop_square, load_normalized_image


def test_load_normalized_image_applies_exif_orientation():
    image = Image.new("RGB", (12, 20), (200, 50, 50))
    exif = Image.Exif()
    exif[274] = 6
    source = BytesIO()
    image.save(source, format="JPEG", exif=exif)
    source.seek(0)

    normalized = load_normalized_image(source)

    assert normalized.size == (20, 12)
    assert normalized.mode == "RGBA"


def test_crop_square_uses_center_of_image():
    image = Image.new("RGBA", (20, 10), (255, 0, 0, 255))
    for y in range(10):
        for x in range(5, 15):
            image.putpixel((x, y), (0, 255, 0, 255))

    cropped = crop_square(image)

    assert cropped.size == (10, 10)
    assert cropped.getpixel((0, 0)) == (0, 255, 0, 255)


@pytest.mark.parametrize("source", [BytesIO(b""), BytesIO(b"not-an-image")])
def test_load_normalized_image_rejects_invalid_files(source):
    with pytest.raises(InvalidImageError, match="损坏|不受支持"):
        load_normalized_image(source)


def test_load_normalized_image_rejects_tiny_image():
    image = Image.new("RGB", (7, 20), (0, 0, 0))
    source = BytesIO()
    image.save(source, format="PNG")
    source.seek(0)

    with pytest.raises(InvalidImageError, match="尺寸过小"):
        load_normalized_image(source)
