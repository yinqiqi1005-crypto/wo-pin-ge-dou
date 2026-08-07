from collections import Counter
from dataclasses import dataclass

type RGB = tuple[int, int, int]
type CellCode = str | None


@dataclass(frozen=True, slots=True)
class BeadColor:
    code: str
    name: str
    rgb: RGB

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("A bead color code cannot be empty.")
        if len(self.rgb) != 3 or any(channel < 0 or channel > 255 for channel in self.rgb):
            raise ValueError(f"Invalid RGB value for {self.code}: {self.rgb}")


@dataclass(frozen=True, slots=True)
class BeadPalette:
    code: str
    name: str
    colors: tuple[BeadColor, ...]

    def __post_init__(self) -> None:
        if not self.colors:
            raise ValueError("A bead palette must contain at least one color.")
        codes = [color.code for color in self.colors]
        if len(codes) != len(set(codes)):
            raise ValueError("Bead color codes must be unique within a palette.")

    @property
    def by_code(self) -> dict[str, BeadColor]:
        return {color.code: color for color in self.colors}


@dataclass(frozen=True, slots=True)
class PatternGrid:
    width: int
    height: int
    cells: tuple[tuple[CellCode, ...], ...]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Pattern dimensions must be positive.")
        if len(self.cells) != self.height:
            raise ValueError("Pattern row count does not match its height.")
        if any(len(row) != self.width for row in self.cells):
            raise ValueError("Pattern column count does not match its width.")

    @property
    def material_counts(self) -> dict[str, int]:
        counts = Counter(cell for row in self.cells for cell in row if cell is not None)
        return dict(sorted(counts.items()))

    @property
    def total_beads(self) -> int:
        return sum(self.material_counts.values())

    @property
    def blank_cells(self) -> int:
        return self.width * self.height - self.total_beads

    @property
    def color_count(self) -> int:
        return len(self.material_counts)


@dataclass(frozen=True, slots=True)
class PatternResult:
    grid: PatternGrid
    palette: BeadPalette
    color_limit: int

    @property
    def material_counts(self) -> dict[str, int]:
        return self.grid.material_counts

    @property
    def total_beads(self) -> int:
        return self.grid.total_beads
