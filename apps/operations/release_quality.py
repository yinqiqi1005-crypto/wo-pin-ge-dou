import csv
from dataclasses import dataclass
from pathlib import Path

from apps.operations.physical_validation import (
    PhysicalValidationError,
    evaluate_physical_validation,
)
from apps.operations.release_evidence import (
    OperationalMetrics,
    ReleaseEvidenceError,
    validate_deployment_report,
)
from apps.operations.usability_walkthrough import (
    UsabilityWalkthroughError,
    evaluate_usability_walkthrough,
)


class ReleaseQualityError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseQualitySummary:
    case_count: int
    file_success_rate: float
    subject_recognizable_rate: float
    severe_subject_error_rate: float
    making_feasible_rate: float
    advanced_conformance_rate: float
    automatic_retry_rate: float
    physical_case_count: int
    usability_task_count: int


REQUIRED_COLUMNS = {
    "case_id",
    "category",
    "formal_conversion",
    "material_consistency",
    "human_subject_recognizable",
    "human_severe_subject_error",
    "human_making_feasible",
    "human_advanced_conformance",
    "human_review",
}


def _rate(rows, field, passing_value):
    return sum(row[field] == passing_value for row in rows) / len(rows)


def _validate_values(rows, field, allowed):
    invalid = sorted({row[field] for row in rows if row[field] not in allowed})
    if invalid:
        raise ReleaseQualityError(f"{field} contains invalid values: {', '.join(invalid)}")


def evaluate_release_quality(
    results_path,
    *,
    operational_metrics: OperationalMetrics,
    open_critical_issues,
    deployment_report_path,
    physical_results_path,
    usability_results_path,
):
    path = Path(results_path)
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ReleaseQualityError(f"Missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    if len(rows) != 40:
        raise ReleaseQualityError(f"Expected 40 reviewed cases, got {len(rows)}.")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ReleaseQualityError("case_id values must be unique.")
    if any(row["human_review"] != "complete" for row in rows):
        pending = sum(row["human_review"] != "complete" for row in rows)
        raise ReleaseQualityError(f"Human review is incomplete for {pending} cases.")

    _validate_values(rows, "formal_conversion", {"pass", "fail"})
    _validate_values(rows, "material_consistency", {"pass", "fail"})
    _validate_values(rows, "human_subject_recognizable", {"pass", "fail"})
    _validate_values(rows, "human_severe_subject_error", {"yes", "no"})
    _validate_values(rows, "human_making_feasible", {"pass", "fail"})
    _validate_values(
        rows,
        "human_advanced_conformance",
        {"pass", "fail", "not_applicable"},
    )

    if operational_metrics.generation_attempts <= 0:
        raise ReleaseQualityError("No generation attempts are recorded in the database.")
    if not 0 <= operational_metrics.retried_tasks <= operational_metrics.generation_attempts:
        raise ReleaseQualityError("Operational retry metrics are inconsistent.")
    if (
        operational_metrics.wrong_charge_count < 0
        or operational_metrics.unfinished_task_count < 0
        or open_critical_issues < 0
    ):
        raise ReleaseQualityError("Operational counters cannot be negative.")

    advanced_rows = [row for row in rows if row["human_advanced_conformance"] != "not_applicable"]
    if len(advanced_rows) < 3:
        raise ReleaseQualityError("At least 3 advanced creation cases must be reviewed.")

    try:
        physical_summary = evaluate_physical_validation(physical_results_path)
        usability_summary = evaluate_usability_walkthrough(usability_results_path)
        validate_deployment_report(deployment_report_path)
    except (PhysicalValidationError, ReleaseEvidenceError, UsabilityWalkthroughError) as exc:
        raise ReleaseQualityError(str(exc)) from exc

    summary = ReleaseQualitySummary(
        case_count=len(rows),
        file_success_rate=_rate(rows, "formal_conversion", "pass"),
        subject_recognizable_rate=_rate(rows, "human_subject_recognizable", "pass"),
        severe_subject_error_rate=_rate(rows, "human_severe_subject_error", "yes"),
        making_feasible_rate=_rate(rows, "human_making_feasible", "pass"),
        advanced_conformance_rate=_rate(
            advanced_rows,
            "human_advanced_conformance",
            "pass",
        ),
        automatic_retry_rate=operational_metrics.automatic_retry_rate,
        physical_case_count=physical_summary.case_count,
        usability_task_count=usability_summary.task_count,
    )

    failures = []
    if any(row["material_consistency"] != "pass" for row in rows):
        failures.append("technical data consistency is below 100%")
    if summary.file_success_rate < 0.95:
        failures.append("pattern file generation success rate is below 95%")
    if summary.subject_recognizable_rate < 0.85:
        failures.append("subject recognizability is below 85%")
    if summary.severe_subject_error_rate >= 0.05:
        failures.append("severe subject error rate is not below 5%")
    if summary.making_feasible_rate < 0.85:
        failures.append("making feasibility is below 85%")
    if summary.advanced_conformance_rate < 0.85:
        failures.append("advanced creation conformance is below 85%")
    if summary.automatic_retry_rate >= 0.15:
        failures.append("automatic retry rate is not below 15%")
    if operational_metrics.wrong_charge_count != 0:
        failures.append("system failures caused incorrect image charges")
    if operational_metrics.unfinished_task_count != 0:
        failures.append("generation tasks remain unfinished")
    if open_critical_issues != 0:
        failures.append("P0 or P1 issues remain open")
    if failures:
        raise ReleaseQualityError("; ".join(failures) + ".")
    return summary
