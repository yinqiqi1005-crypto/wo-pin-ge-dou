import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class PhysicalValidationError(ValueError):
    pass


REQUIRED_COLUMNS = {
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
}
REQUIRED_CATEGORIES = {"person", "pet", "object"}
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class PhysicalValidationSummary:
    case_count: int
    total_planned_beads: int
    total_actual_beads: int
    total_making_minutes: int


def _integer(row, field, *, positive=False):
    try:
        value = int(row[field])
    except (TypeError, ValueError) as exc:
        raise PhysicalValidationError(
            f"{row.get('case_id', 'unknown')} has invalid {field}."
        ) from exc
    if positive and value <= 0:
        raise PhysicalValidationError(f"{row['case_id']} requires positive {field}.")
    return value


def _resolve_photo(csv_path, row):
    raw_path = Path(row["finished_photo"])
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise PhysicalValidationError(
            f"{row['case_id']} finished_photo must stay inside the evidence directory."
        )
    photo = (csv_path.parent / raw_path).resolve()
    evidence_root = csv_path.parent.resolve()
    if not photo.is_relative_to(evidence_root):
        raise PhysicalValidationError(
            f"{row['case_id']} finished_photo must stay inside the evidence directory."
        )
    if photo.suffix.lower() not in PHOTO_SUFFIXES or not photo.is_file():
        raise PhysicalValidationError(f"{row['case_id']} finished photo is missing.")
    try:
        with Image.open(photo) as image:
            image.verify()
    except (OSError, UnidentifiedImageError) as exc:
        raise PhysicalValidationError(
            f"{row['case_id']} finished photo is not a valid image."
        ) from exc


def evaluate_physical_validation(results_path):
    path = Path(results_path)
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise PhysicalValidationError(
                "Physical validation is missing columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)

    if len(rows) != 3 or {row["category"] for row in rows} != REQUIRED_CATEGORIES:
        raise PhysicalValidationError(
            "Physical validation requires one person, pet and object case."
        )
    if len({row["case_id"] for row in rows}) != 3:
        raise PhysicalValidationError("Physical validation case_id values must be unique.")
    pending = [row["case_id"] for row in rows if row["status"] != "complete"]
    if pending:
        raise PhysicalValidationError(
            "Physical validation is incomplete for: " + ", ".join(pending)
        )

    total_planned = 0
    total_actual = 0
    total_minutes = 0
    for row in rows:
        if _integer(row, "grid_size", positive=True) != 30:
            raise PhysicalValidationError(f"{row['case_id']} must use a 30x30 pattern.")
        planned = _integer(row, "planned_beads", positive=True)
        actual = _integer(row, "actual_beads", positive=True)
        difference = _integer(row, "bead_difference")
        if difference != actual - planned:
            raise PhysicalValidationError(
                f"{row['case_id']} bead_difference must equal actual minus planned beads."
            )
        minutes = _integer(row, "making_minutes", positive=True)
        if row["ironing_result"] != "pass":
            raise PhysicalValidationError(f"{row['case_id']} ironing result did not pass.")
        if not row["reviewer"].strip():
            raise PhysicalValidationError(f"{row['case_id']} requires a reviewer.")
        try:
            reviewed_on = date.fromisoformat(row["review_date"])
        except ValueError as exc:
            raise PhysicalValidationError(f"{row['case_id']} requires an ISO review_date.") from exc
        if reviewed_on > date.today():
            raise PhysicalValidationError(f"{row['case_id']} review_date cannot be in the future.")
        _resolve_photo(path, row)
        total_planned += planned
        total_actual += actual
        total_minutes += minutes

    return PhysicalValidationSummary(
        case_count=len(rows),
        total_planned_beads=total_planned,
        total_actual_beads=total_actual,
        total_making_minutes=total_minutes,
    )
