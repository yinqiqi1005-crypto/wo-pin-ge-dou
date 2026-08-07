from services.image_processing.cleanup import clean_isolated_cells
from services.image_processing.models import PatternGrid


def test_cleanup_replaces_only_fully_isolated_cell_with_majority():
    grid = PatternGrid(
        width=3,
        height=3,
        cells=(("A", "A", "A"), ("A", "B", "A"), ("A", "A", "A")),
    )

    cleaned = clean_isolated_cells(grid)

    assert cleaned.cells[1][1] == "A"


def test_cleanup_does_not_replace_connected_detail():
    grid = PatternGrid(
        width=3,
        height=3,
        cells=(("A", "A", "A"), ("A", "B", "B"), ("A", "A", "A")),
    )

    cleaned = clean_isolated_cells(grid)

    assert cleaned.cells[1][1] == "B"
    assert cleaned.cells[1][2] == "B"


def test_cleanup_keeps_isolated_cell_near_blank_background():
    grid = PatternGrid(
        width=3,
        height=3,
        cells=((None, None, None), (None, "B", None), (None, None, None)),
    )

    cleaned = clean_isolated_cells(grid)

    assert cleaned == grid
