import pytest
from PIL import Image

from services.image_processing import apply_basic_background


def test_remove_background_makes_corner_color_transparent():
    image = Image.new("RGBA", (20, 20), (250, 250, 250, 255))
    for y in range(5, 15):
        for x in range(5, 15):
            image.putpixel((x, y), (200, 40, 40, 255))

    result = apply_basic_background(image, mode="remove")

    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((10, 10))[3] == 255


@pytest.mark.parametrize("mode", ["keep", "simplify"])
def test_keep_and_simplify_preserve_alpha(mode):
    image = Image.new("RGBA", (10, 10), (50, 60, 70, 123))

    result = apply_basic_background(image, mode=mode)

    assert result.getpixel((5, 5)) == (50, 60, 70, 123)


def test_unknown_background_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported background mode"):
        apply_basic_background(Image.new("RGBA", (10, 10)), mode="unknown")
