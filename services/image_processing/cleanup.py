from collections import Counter

from .models import PatternGrid

NEIGHBOR_OFFSETS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def clean_isolated_cells(grid: PatternGrid, *, minimum_neighbors: int = 3) -> PatternGrid:
    """Replace fully isolated colored cells only when surrounded by a clear majority."""
    updated = [list(row) for row in grid.cells]

    for y in range(grid.height):
        for x in range(grid.width):
            current = grid.cells[y][x]
            if current is None:
                continue

            neighbors = [
                grid.cells[y + dy][x + dx]
                for dx, dy in NEIGHBOR_OFFSETS
                if 0 <= x + dx < grid.width and 0 <= y + dy < grid.height
            ]
            non_blank = [code for code in neighbors if code is not None]
            if current in non_blank or len(non_blank) < minimum_neighbors:
                continue

            replacement, count = Counter(non_blank).most_common(1)[0]
            if count >= minimum_neighbors:
                updated[y][x] = replacement

    return PatternGrid(
        width=grid.width,
        height=grid.height,
        cells=tuple(tuple(row) for row in updated),
    )
