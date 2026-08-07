from io import BytesIO

import pytest
from PIL import Image


@pytest.fixture
def four_color_png() -> BytesIO:
    image = Image.new("RGB", (20, 20))
    pixels = image.load()
    colors = ((220, 60, 60), (60, 170, 80), (60, 110, 210), (245, 220, 100))
    for y in range(20):
        for x in range(20):
            index = (x >= 10) + 2 * (y >= 10)
            pixels[x, y] = colors[index]

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


@pytest.fixture
def transparent_png() -> BytesIO:
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for y in range(5, 15):
        for x in range(5, 15):
            image.putpixel((x, y), (210, 55, 60, 255))

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
