from .exceptions import PatternValidationError
from .models import BeadPalette, PatternGrid


def validate_pattern(grid: PatternGrid, *, palette: BeadPalette, color_limit: int) -> None:
    errors: list[str] = []
    allowed_codes = set(palette.by_code)
    used_codes = set(grid.material_counts)
    invalid_codes = sorted(used_codes - allowed_codes)

    if invalid_codes:
        errors.append(f"图纸包含色板中不存在的颜色编号：{', '.join(invalid_codes)}")
    if grid.color_count > color_limit:
        errors.append(f"实际颜色数量 {grid.color_count} 超过限制 {color_limit}")

    counted_cells = sum(grid.material_counts.values())
    traversed_cells = sum(cell is not None for row in grid.cells for cell in row)
    if counted_cells != traversed_cells:
        errors.append("材料清单数量与非空网格数量不一致")
    if grid.total_beads + grid.blank_cells != grid.width * grid.height:
        errors.append("拼豆数量与空白格数量之和不等于网格总数")

    if errors:
        raise PatternValidationError("；".join(errors))
