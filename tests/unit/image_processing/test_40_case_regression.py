from io import BytesIO
from time import monotonic

from services.image_processing import create_pattern
from tests.fixtures.image_cases import CASES, build_case_image


def test_40_legal_images_pass_formal_conversion_and_data_consistency():
    assert len(CASES) == 40
    started = monotonic()
    category_counts = {}

    for case in CASES:
        category_counts[case.category] = category_counts.get(case.category, 0) + 1
        result = create_pattern(
            BytesIO(build_case_image(case)),
            size=case.grid_size,
            color_limit=case.color_limit,
        )
        assert result.grid.width == case.grid_size
        assert len(result.material_counts) <= case.color_limit
        assert sum(result.material_counts.values()) == result.grid.total_beads

    assert category_counts == {
        "person": 8,
        "pet": 8,
        "object": 8,
        "illustration": 8,
        "special": 8,
    }
    assert monotonic() - started < 20
