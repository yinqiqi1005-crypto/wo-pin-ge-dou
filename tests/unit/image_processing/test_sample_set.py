from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from services.image_processing import create_pattern, render_effect_preview, validate_pattern

SAMPLE_NAMES = (
    "solid",
    "quadrants",
    "transparent-circle",
    "horizontal-gradient",
    "vertical-stripes",
    "checkerboard",
    "simple-face",
    "low-contrast",
    "diagonal",
    "small-details",
)


def build_sample(name: str) -> BytesIO:
    image = Image.new("RGBA", (96, 72), (245, 240, 230, 255))
    draw = ImageDraw.Draw(image)

    if name == "solid":
        draw.rectangle((0, 0, 95, 71), fill=(205, 52, 58, 255))
    elif name == "quadrants":
        draw.rectangle((0, 0, 47, 35), fill=(205, 52, 58, 255))
        draw.rectangle((48, 0, 95, 35), fill=(46, 102, 180, 255))
        draw.rectangle((0, 36, 47, 71), fill=(76, 155, 83, 255))
        draw.rectangle((48, 36, 95, 71), fill=(246, 196, 45, 255))
    elif name == "transparent-circle":
        image = Image.new("RGBA", (96, 72), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((24, 12, 72, 60), fill=(236, 112, 145, 255))
    elif name == "horizontal-gradient":
        for x in range(96):
            draw.line((x, 0, x, 71), fill=(40 + x * 2, 100, 210 - x, 255))
    elif name == "vertical-stripes":
        colors = ((35, 56, 112, 255), (160, 210, 232, 255), (250, 248, 242, 255))
        for x in range(0, 96, 8):
            draw.rectangle((x, 0, x + 7, 71), fill=colors[(x // 8) % len(colors)])
    elif name == "checkerboard":
        for y in range(0, 72, 8):
            for x in range(0, 96, 8):
                fill = (31, 31, 31, 255) if (x // 8 + y // 8) % 2 else (250, 248, 242, 255)
                draw.rectangle((x, y, x + 7, y + 7), fill=fill)
    elif name == "simple-face":
        draw.ellipse((24, 6, 72, 66), fill=(247, 205, 174, 255))
        draw.ellipse((36, 28, 41, 34), fill=(31, 31, 31, 255))
        draw.ellipse((55, 28, 60, 34), fill=(31, 31, 31, 255))
        draw.arc((39, 36, 57, 53), start=10, end=170, fill=(130, 36, 45, 255), width=3)
    elif name == "low-contrast":
        draw.rectangle((18, 10, 78, 62), fill=(220, 200, 180, 255))
        draw.ellipse((32, 20, 64, 52), fill=(205, 187, 169, 255))
    elif name == "diagonal":
        for offset in range(-72, 96, 12):
            draw.line((offset, 71, offset + 72, 0), fill=(132, 84, 178, 255), width=6)
    elif name == "small-details":
        for y in range(4, 72, 8):
            for x in range(4, 96, 8):
                fill = (239, 131, 48, 255) if (x + y) % 16 else (53, 161, 157, 255)
                draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=fill)
    else:
        raise ValueError(f"Unknown sample: {name}")

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


@pytest.mark.parametrize("sample_name", SAMPLE_NAMES)
def test_ten_image_regression_set_produces_valid_patterns(sample_name):
    result = create_pattern(build_sample(sample_name), size=30, color_limit=12)
    preview = render_effect_preview(result.grid, palette=result.palette)

    validate_pattern(result.grid, palette=result.palette, color_limit=12)
    assert result.grid.width == 30
    assert result.grid.height == 30
    assert result.grid.color_count <= 12
    assert preview.size == (360, 360)
