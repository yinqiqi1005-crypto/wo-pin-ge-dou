import csv
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
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


def test_40_case_result_table_covers_every_fixed_case_without_false_human_claims():
    report_path = Path(__file__).parents[3] / "docs" / "test-results-40.csv"
    with report_path.open(encoding="utf-8", newline="") as report:
        rows = list(csv.DictReader(report))

    assert len(rows) == 40
    assert {row["case_id"] for row in rows} == {case.case_id for case in CASES}
    cases_by_id = {case.case_id: case for case in CASES}
    assert all(
        row["expected_subject"] == cases_by_id[row["case_id"]].expected_subject
        and row["expected_risk"] == cases_by_id[row["case_id"]].expected_risk
        and int(row["grid_size"]) == cases_by_id[row["case_id"]].grid_size
        and int(row["color_limit"]) == cases_by_id[row["case_id"]].color_limit
        for row in rows
    )
    assert all(row["formal_conversion"] == "pass" for row in rows)
    assert all(row["material_consistency"] == "pass" for row in rows)
    assert all(row["human_review"] == "pending" for row in rows)
    assert all(row["human_subject_recognizable"] == "pending" for row in rows)
    assert all(row["human_severe_subject_error"] == "pending" for row in rows)
    assert all(row["human_making_feasible"] == "pending" for row in rows)
    assert all(row["human_advanced_conformance"] == "pending" for row in rows)


def test_multiple_image_conversions_run_concurrently_without_cross_task_state():
    cases = CASES[:8]

    def convert(case):
        result = create_pattern(
            BytesIO(build_case_image(case)),
            size=case.grid_size,
            color_limit=case.color_limit,
        )
        return case.case_id, result.grid.width, result.total_beads

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(convert, cases))

    assert [result[0] for result in results] == [case.case_id for case in cases]
    assert [result[1] for result in results] == [case.grid_size for case in cases]
    assert all(total > 0 for _, _, total in results)
