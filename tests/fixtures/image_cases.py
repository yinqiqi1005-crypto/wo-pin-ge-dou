from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class ImageCase:
    case_id: str
    category: str
    expected_subject: str
    expected_risk: str
    grid_size: int
    color_limit: int


CASES = tuple(
    ImageCase(
        case_id=f"{category[:3]}-{index:02d}",
        category=category,
        expected_subject=subject,
        expected_risk=risk if index in {7, 8} else "none",
        grid_size=(30, 50, 70)[(index - 1) % 3],
        color_limit=(12, 24, 36)[(index - 1) % 3],
    )
    for category, subject, risk in (
        ("person", "中心人物", "low_contrast"),
        ("pet", "中心宠物", "dark_image"),
        ("object", "中心物品", "small_detail"),
        ("illustration", "中心插画", "many_colors"),
        ("special", "特殊图片主体", "transparency_or_text"),
    )
    for index in range(1, 9)
)


def build_case_image(case: ImageCase) -> bytes:
    index = int(case.case_id[-2:])
    size = 96 if index == 8 else 256
    mode = "RGBA" if case.category == "special" else "RGB"
    background = (235, 230, 220, 0) if mode == "RGBA" else (235, 230, 220)
    image = Image.new(mode, (size, size), background)
    draw = ImageDraw.Draw(image)
    scale = size / 256

    def box(values):
        return tuple(round(value * scale) for value in values)

    accent = (65 + index * 12, 85 + index * 8, 175 - index * 5, 255)
    if mode == "RGB":
        accent = accent[:3]
    if case.category == "person":
        draw.ellipse(box((88, 35, 168, 115)), fill=accent)
        draw.rounded_rectangle(box((68, 105, 188, 235)), radius=round(22 * scale), fill=accent)
    elif case.category == "pet":
        draw.polygon([box((65, 85)), box((90, 28)), box((120, 85))], fill=accent)
        draw.polygon([box((136, 85)), box((166, 28)), box((192, 85))], fill=accent)
        draw.ellipse(box((58, 65, 198, 215)), fill=accent)
    elif case.category == "object":
        draw.rounded_rectangle(box((48, 58, 208, 208)), radius=round(26 * scale), fill=accent)
        draw.rectangle(box((92, 25, 164, 68)), fill=accent)
    elif case.category == "illustration":
        draw.regular_polygon((128 * scale, 128 * scale, 88 * scale), 5, rotation=18, fill=accent)
        draw.ellipse(
            box((98, 98, 158, 158)), fill=(245, 185, 75, 255) if mode == "RGBA" else (245, 185, 75)
        )
    else:
        draw.ellipse(box((55, 55, 201, 201)), fill=accent)
        draw.rectangle(box((112, 75, 144, 181)), fill=(45, 45, 45, 255))
        draw.rectangle(box((75, 112, 181, 144)), fill=(45, 45, 45, 255))

    if index == 7:
        overlay = Image.new(
            mode, image.size, (225, 225, 220, 170) if mode == "RGBA" else (225, 225, 220)
        )
        image = Image.blend(image.convert("RGBA"), overlay.convert("RGBA"), 0.55)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
