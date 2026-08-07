from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from skimage import data


@dataclass(frozen=True)
class ImageCase:
    case_id: str
    category: str
    expected_subject: str
    expected_risk: str
    grid_size: int
    color_limit: int
    source_name: str


SOURCES = {
    "person": ("astronaut", "camera", "lfw_subset"),
    "pet": ("cat", "horse", "chelsea"),
    "object": ("coffee", "coins", "clock", "rocket"),
    "illustration": ("logo", "colorwheel", "checkerboard", "binary_blobs"),
    "special": ("page", "text", "hubble_deep_field", "retina"),
}

CASES = tuple(
    ImageCase(
        case_id=f"{category[:3]}-{index:02d}",
        category=category,
        expected_subject=subject,
        expected_risk=risk if index in {7, 8} else "none",
        grid_size=(30, 50, 70)[(index - 1) % 3],
        color_limit=(12, 24, 36)[(index - 1) % 3],
        source_name=SOURCES[category][(index - 1) % len(SOURCES[category])],
    )
    for category, subject, risk in (
        ("person", "人物或人脸", "low_contrast"),
        ("pet", "猫或马", "dark_image"),
        ("object", "日常物品", "small_detail"),
        ("illustration", "图形或插画", "many_colors"),
        ("special", "复杂特殊内容", "transparency_or_text"),
    )
    for index in range(1, 9)
)


def _to_pillow(array, *, variant):
    if array.ndim == 3 and array.shape[0] > 10 and array.shape[1] <= 32:
        array = array[variant % array.shape[0]]
    if array.dtype == np.bool_:
        array = array.astype(np.uint8) * 255
    elif np.issubdtype(array.dtype, np.floating):
        maximum = float(array.max()) or 1
        array = np.clip(array / maximum * 255, 0, 255).astype(np.uint8)
    else:
        array = np.clip(array, 0, 255).astype(np.uint8)
    image = Image.fromarray(array)
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")
    centering = ((0.35, 0.5), (0.5, 0.5), (0.65, 0.5))[variant % 3]
    return ImageOps.fit(image, (256, 256), method=Image.Resampling.LANCZOS, centering=centering)


def build_case_image(case: ImageCase) -> bytes:
    variant = int(case.case_id[-2:])
    source = getattr(data, case.source_name)()
    image = _to_pillow(source, variant=variant)
    if variant % 2 == 0:
        image = ImageOps.mirror(image)

    if case.expected_risk == "low_contrast":
        image = ImageEnhance.Contrast(image).enhance(0.22)
    elif case.expected_risk == "dark_image":
        image = ImageEnhance.Brightness(image).enhance(0.2)
    elif case.expected_risk == "small_detail":
        thumbnail = image.resize((96, 96), Image.Resampling.LANCZOS)
        image = Image.new("RGB", (256, 256), (245, 245, 245))
        image.paste(thumbnail.convert("RGB"), (80, 80))
    elif case.expected_risk == "transparency_or_text":
        image = image.convert("RGBA")
        image.putalpha(Image.new("L", image.size, 210 if variant == 7 else 150))

    if variant == 8:
        image = image.resize((96, 96), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
