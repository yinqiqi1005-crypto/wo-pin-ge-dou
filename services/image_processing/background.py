import numpy as np
from PIL import Image


def apply_basic_background(
    image: Image.Image, *, mode: str, tolerance: float = 38.0
) -> Image.Image:
    """Apply deterministic v1 background handling without a segmentation model."""
    rgba = image.convert("RGBA")
    if mode in {"keep", "simplify"}:
        return rgba
    if mode != "remove":
        raise ValueError(f"Unsupported background mode: {mode}")

    pixels = np.asarray(rgba, dtype=np.uint8).copy()
    corners = np.asarray(
        (
            pixels[0, 0, :3],
            pixels[0, -1, :3],
            pixels[-1, 0, :3],
            pixels[-1, -1, :3],
        ),
        dtype=np.float64,
    )
    background = np.median(corners, axis=0)
    distance = np.linalg.norm(pixels[:, :, :3].astype(np.float64) - background, axis=2)
    pixels[distance <= tolerance, 3] = 0
    return Image.fromarray(pixels, mode="RGBA")
