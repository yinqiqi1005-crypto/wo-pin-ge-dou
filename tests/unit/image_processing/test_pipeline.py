from io import BytesIO

import pytest

from services.image_processing import (
    DEFAULT_PALETTE,
    create_pattern,
    render_effect_preview,
    render_grid_preview,
    validate_pattern,
)


@pytest.mark.parametrize("size", [30, 50, 70])
def test_create_pattern_supports_configured_sizes(four_color_png, size):
    result = create_pattern(four_color_png, size=size, color_limit=12)

    assert result.grid.width == size
    assert result.grid.height == size
    assert len(result.grid.cells) == size
    assert all(len(row) == size for row in result.grid.cells)


@pytest.mark.parametrize("color_limit", [12, 24, 36])
def test_create_pattern_uses_only_legal_colors(four_color_png, color_limit):
    result = create_pattern(four_color_png, size=30, color_limit=color_limit)
    allowed_codes = set(DEFAULT_PALETTE.by_code)

    assert set(result.material_counts) <= allowed_codes
    assert len(result.material_counts) <= color_limit
    validate_pattern(result.grid, palette=result.palette, color_limit=color_limit)


def test_transparent_pixels_become_blank_cells(transparent_png):
    result = create_pattern(transparent_png, size=30, color_limit=12)

    assert result.grid.blank_cells > 0
    assert result.grid.total_beads > 0
    assert result.grid.blank_cells + result.grid.total_beads == 30 * 30


def test_material_counts_equal_non_blank_cells(four_color_png):
    result = create_pattern(four_color_png, size=50, color_limit=24)
    traversed_non_blank = sum(cell is not None for row in result.grid.cells for cell in row)

    assert sum(result.material_counts.values()) == traversed_non_blank
    assert result.total_beads == traversed_non_blank


def test_same_input_and_parameters_are_deterministic(four_color_png):
    source_bytes = four_color_png.getvalue()

    first = create_pattern(BytesIO(source_bytes), size=30, color_limit=12)
    second = create_pattern(BytesIO(source_bytes), size=30, color_limit=12)

    assert first.grid == second.grid
    assert first.material_counts == second.material_counts


def test_rendered_previews_match_grid_dimensions(four_color_png):
    result = create_pattern(four_color_png, size=30, color_limit=12)

    effect = render_effect_preview(result.grid, palette=result.palette, bead_pixels=10)
    numbered = render_grid_preview(result.grid, palette=result.palette, cell_pixels=20)

    assert effect.size == (300, 300)
    assert numbered.size == (601, 601)


def test_rendered_effect_keeps_blank_cells_transparent(transparent_png):
    result = create_pattern(transparent_png, size=30, color_limit=12)
    effect = render_effect_preview(result.grid, palette=result.palette, bead_pixels=10)

    assert effect.getpixel((5, 5))[3] == 0
    assert effect.getpixel((155, 155))[3] == 255


@pytest.mark.parametrize("size", [29, 31, 100])
def test_create_pattern_rejects_unsupported_size(four_color_png, size):
    with pytest.raises(ValueError, match="Unsupported grid size"):
        create_pattern(four_color_png, size=size, color_limit=12)


@pytest.mark.parametrize("color_limit", [1, 16, 100])
def test_create_pattern_rejects_unsupported_color_limit(four_color_png, color_limit):
    with pytest.raises(ValueError, match="Unsupported color limit"):
        create_pattern(four_color_png, size=30, color_limit=color_limit)


def test_create_pattern_rejects_palette_smaller_than_limit(four_color_png):
    from services.image_processing.models import BeadPalette

    small_palette = BeadPalette(code="small", name="Small", colors=DEFAULT_PALETTE.colors[:2])

    with pytest.raises(ValueError, match="palette size"):
        create_pattern(
            four_color_png,
            size=30,
            color_limit=12,
            palette=small_palette,
        )
