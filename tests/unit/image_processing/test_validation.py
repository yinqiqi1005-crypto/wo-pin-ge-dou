import pytest

from services.image_processing import DEFAULT_PALETTE, PatternValidationError, validate_pattern
from services.image_processing.models import PatternGrid


def test_validation_rejects_color_outside_palette():
    grid = PatternGrid(width=1, height=1, cells=(("UNKNOWN",),))

    with pytest.raises(PatternValidationError, match="不存在"):
        validate_pattern(grid, palette=DEFAULT_PALETTE, color_limit=12)


def test_validation_rejects_too_many_colors():
    codes = tuple(color.code for color in DEFAULT_PALETTE.colors[:13])
    grid = PatternGrid(width=13, height=1, cells=(codes,))

    with pytest.raises(PatternValidationError, match="超过限制"):
        validate_pattern(grid, palette=DEFAULT_PALETTE, color_limit=12)
