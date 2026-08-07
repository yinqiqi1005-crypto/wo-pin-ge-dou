from collections.abc import Iterable

import numpy as np
from PIL import Image
from skimage.color import rgb2lab

from .models import BeadPalette, PatternGrid

SUPPORTED_GRID_SIZES = frozenset({30, 50, 70})
SUPPORTED_COLOR_LIMITS = frozenset({12, 24, 36})
ALPHA_BLANK_THRESHOLD = 128


def _nearest_palette_codes(
    colors: Iterable[tuple[int, int, int]], palette: BeadPalette
) -> dict[tuple[int, int, int], str]:
    unique_colors = tuple(dict.fromkeys(colors))
    if not unique_colors:
        return {}

    source_rgb = np.asarray(unique_colors, dtype=np.float64).reshape((-1, 1, 3)) / 255.0
    palette_rgb = np.asarray([color.rgb for color in palette.colors], dtype=np.float64)
    palette_rgb = palette_rgb.reshape((1, -1, 3)) / 255.0

    source_lab = rgb2lab(source_rgb)
    palette_lab = rgb2lab(palette_rgb)
    distances = np.linalg.norm(source_lab - palette_lab, axis=2)
    nearest_indexes = np.argmin(distances, axis=1)

    return {
        source: palette.colors[int(index)].code
        for source, index in zip(unique_colors, nearest_indexes, strict=True)
    }


def image_to_grid(
    image: Image.Image,
    *,
    size: int,
    color_limit: int,
    palette: BeadPalette,
) -> PatternGrid:
    if size not in SUPPORTED_GRID_SIZES:
        raise ValueError(f"Unsupported grid size: {size}")
    if color_limit not in SUPPORTED_COLOR_LIMITS:
        raise ValueError(f"Unsupported color limit: {color_limit}")
    if color_limit > len(palette.colors):
        raise ValueError("Color limit cannot exceed the selected palette size.")

    rgba = image.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)

    # Quantize only RGB data. Transparency is restored as empty cells afterwards.
    quantized_rgb = rgba.convert("RGB").quantize(
        colors=color_limit, method=Image.Quantize.MEDIANCUT
    )
    rgb = np.asarray(quantized_rgb.convert("RGB"), dtype=np.uint8)
    opaque_colors = [
        tuple(int(channel) for channel in rgb[y, x])
        for y in range(size)
        for x in range(size)
        if alpha[y, x] >= ALPHA_BLANK_THRESHOLD
    ]
    mapping = _nearest_palette_codes(opaque_colors, palette)

    rows: list[tuple[str | None, ...]] = []
    for y in range(size):
        row: list[str | None] = []
        for x in range(size):
            if alpha[y, x] < ALPHA_BLANK_THRESHOLD:
                row.append(None)
            else:
                source_rgb = tuple(int(channel) for channel in rgb[y, x])
                row.append(mapping[source_rgb])
        rows.append(tuple(row))

    return PatternGrid(width=size, height=size, cells=tuple(rows))
