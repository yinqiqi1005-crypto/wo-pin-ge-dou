import pytest

from services.image_processing.models import BeadColor, BeadPalette, PatternGrid


def test_palette_rejects_duplicate_codes():
    with pytest.raises(ValueError, match="unique"):
        BeadPalette(
            code="duplicate",
            name="Duplicate",
            colors=(
                BeadColor("A", "First", (0, 0, 0)),
                BeadColor("A", "Second", (255, 255, 255)),
            ),
        )


def test_grid_rejects_wrong_row_width():
    with pytest.raises(ValueError, match="column count"):
        PatternGrid(width=2, height=1, cells=(("A",),))


def test_grid_material_counts_and_blank_cells():
    grid = PatternGrid(width=2, height=2, cells=(("B", None), ("A", "B")))

    assert grid.material_counts == {"A": 1, "B": 2}
    assert grid.total_beads == 3
    assert grid.blank_cells == 1
    assert grid.color_count == 2
