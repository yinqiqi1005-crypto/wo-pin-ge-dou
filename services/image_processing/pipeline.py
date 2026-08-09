from .cleanup import clean_isolated_cells
from .converter import image_to_grid
from .models import BeadPalette, PatternResult
from .normalize import ImageSource, crop_to_ratio, load_normalized_image
from .palette import DEFAULT_PALETTE
from .validation import validate_pattern


def create_pattern(
    source: ImageSource,
    *,
    size: int | None = None,
    width: int | None = None,
    height: int | None = None,
    color_limit: int,
    palette: BeadPalette = DEFAULT_PALETTE,
    clean_isolated: bool = True,
) -> PatternResult:
    if size is not None:
        width = width or size
        height = height or size
    if width is None or height is None:
        raise ValueError("A pattern size or width and height is required.")
    image = load_normalized_image(source)
    cropped = crop_to_ratio(image, width=width, height=height)
    grid = image_to_grid(
        cropped,
        width=width,
        height=height,
        color_limit=color_limit,
        palette=palette,
    )
    if clean_isolated:
        grid = clean_isolated_cells(grid)
    validate_pattern(grid, palette=palette, color_limit=color_limit)
    return PatternResult(grid=grid, palette=palette, color_limit=color_limit)
