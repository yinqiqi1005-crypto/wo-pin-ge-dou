import csv
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from apps.operations.physical_validation import (
    PhysicalValidationError,
    evaluate_physical_validation,
)

FIELDS = (
    "case_id",
    "category",
    "grid_size",
    "planned_beads",
    "actual_beads",
    "bead_difference",
    "color_substitutions",
    "making_minutes",
    "ironing_result",
    "finished_photo",
    "reviewer",
    "review_date",
    "status",
    "notes",
)
REPOSITORY_TEMPLATE = Path(__file__).parents[2] / "docs" / "physical-validation.csv"


def complete_rows():
    rows = []
    for index, (case_id, category, actual) in enumerate(
        (("per-01", "person", 895), ("pet-01", "pet", 900), ("obj-01", "object", 905))
    ):
        rows.append(
            {
                "case_id": case_id,
                "category": category,
                "grid_size": 30,
                "planned_beads": 900,
                "actual_beads": actual,
                "bead_difference": actual - 900,
                "color_substitutions": "无" if index < 2 else "WPD-016 替代 2 颗",
                "making_minutes": 70 + index * 10,
                "ironing_result": "pass",
                "finished_photo": f"photos/{case_id}.png",
                "reviewer": "测试评审人",
                "review_date": date.today().isoformat(),
                "status": "complete",
                "notes": "成品结构稳定",
            }
        )
    return rows


def write_evidence(path, rows, *, create_photos=True):
    if create_photos:
        photo_dir = path.parent / "photos"
        photo_dir.mkdir(parents=True, exist_ok=True)
        for row in rows:
            Image.new("RGB", (32, 32), (180, 90, 70)).save(path.parent / row["finished_photo"])
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_complete_person_pet_and_object_physical_evidence_passes(tmp_path):
    path = tmp_path / "physical.csv"
    write_evidence(path, complete_rows())

    summary = evaluate_physical_validation(path)

    assert summary.case_count == 3
    assert summary.total_planned_beads == 2700
    assert summary.total_actual_beads == 2700
    assert summary.total_making_minutes == 240


def test_repository_physical_validation_template_is_intentionally_pending():
    with pytest.raises(PhysicalValidationError, match="incomplete for: per-01, pet-01, obj-01"):
        evaluate_physical_validation(REPOSITORY_TEMPLATE)


def test_pending_physical_case_cannot_pass(tmp_path):
    rows = complete_rows()
    rows[0]["status"] = "pending"
    path = tmp_path / "physical.csv"
    write_evidence(path, rows)

    with pytest.raises(PhysicalValidationError, match="incomplete for: per-01"):
        evaluate_physical_validation(path)


def test_missing_finished_photo_cannot_pass(tmp_path):
    path = tmp_path / "physical.csv"
    write_evidence(path, complete_rows(), create_photos=False)

    with pytest.raises(PhysicalValidationError, match="finished photo is missing"):
        evaluate_physical_validation(path)


def test_invalid_finished_photo_cannot_pass(tmp_path):
    rows = complete_rows()
    path = tmp_path / "physical.csv"
    write_evidence(path, rows)
    (tmp_path / rows[1]["finished_photo"]).write_text("not an image", encoding="utf-8")

    with pytest.raises(PhysicalValidationError, match="not a valid image"):
        evaluate_physical_validation(path)


def test_actual_bead_difference_must_match_recorded_counts(tmp_path):
    rows = complete_rows()
    rows[2]["bead_difference"] = 0
    path = tmp_path / "physical.csv"
    write_evidence(path, rows)

    with pytest.raises(PhysicalValidationError, match="actual minus planned"):
        evaluate_physical_validation(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.update(grid_size=50), "must use a 30x30"),
        (lambda row: row.update(ironing_result="fail"), "ironing result did not pass"),
        (lambda row: row.update(reviewer=""), "requires a reviewer"),
        (lambda row: row.update(finished_photo="../outside.png"), "inside the evidence"),
    ],
)
def test_each_required_physical_evidence_field_is_enforced(tmp_path, mutation, message):
    rows = complete_rows()
    mutation(rows[0])
    path = tmp_path / "physical.csv"
    write_evidence(path, rows, create_photos=".." not in rows[0]["finished_photo"])

    with pytest.raises(PhysicalValidationError, match=message):
        evaluate_physical_validation(path)
