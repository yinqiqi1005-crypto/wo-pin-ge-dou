from .cleanup import clean_isolated_cells
from .converter import image_to_grid
from .models import BeadPalette, PatternResult
from .normalize import ImageSource, crop_square, load_normalized_image
from .palette import DEFAULT_PALETTE
from .validation import validate_pattern


def create_pattern(
    source: ImageSource,
    *,
    size: int,
    color_limit: int,
    palette: BeadPalette = DEFAULT_PALETTE,
    clean_isolated: bool = True,
) -> PatternResult:
    image = load_normalized_image(source)
    square = crop_square(image)
    grid = image_to_grid(square, size=size, color_limit=color_limit, palette=palette)
    if clean_isolated:
        grid = clean_isolated_cells(grid)
    validate_pattern(grid, palette=palette, color_limit=color_limit)
    return PatternResult(grid=grid, palette=palette, color_limit=color_limit)
