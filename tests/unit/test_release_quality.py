import csv

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.operations.release_quality import (
    ReleaseQualityError,
    evaluate_release_quality,
)

FIELDS = (
    "case_id",
    "category",
    "formal_conversion",
    "material_consistency",
    "human_subject_recognizable",
    "human_severe_subject_error",
    "human_making_feasible",
    "human_advanced_conformance",
    "human_review",
)


def reviewed_rows():
    rows = []
    for index in range(40):
        rows.append(
            {
                "case_id": f"case-{index:02d}",
                "category": "person",
                "formal_conversion": "pass",
                "material_consistency": "pass",
                "human_subject_recognizable": "pass" if index < 34 else "fail",
                "human_severe_subject_error": "yes" if index == 0 else "no",
                "human_making_feasible": "pass" if index < 34 else "fail",
                "human_advanced_conformance": "pass" if index < 3 else "not_applicable",
                "human_review": "complete",
            }
        )
    return rows


def write_results(path, rows):
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(path, **overrides):
    arguments = {
        "generation_attempts": 100,
        "automatic_retries": 14,
        "wrong_charges": 0,
        "open_critical_issues": 0,
        "deployment_smoke_passed": True,
    }
    arguments.update(overrides)
    return evaluate_release_quality(path, **arguments)


def test_release_quality_accepts_exact_thresholds_without_rounding_them_down(tmp_path):
    path = tmp_path / "results.csv"
    write_results(path, reviewed_rows())

    summary = evaluate(path)

    assert summary.case_count == 40
    assert summary.subject_recognizable_rate == 0.85
    assert summary.severe_subject_error_rate == 0.025
    assert summary.making_feasible_rate == 0.85
    assert summary.automatic_retry_rate == 0.14


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda rows: rows[33].update(human_subject_recognizable="fail"),
            "subject recognizability is below 85%",
        ),
        (
            lambda rows: rows[1].update(human_severe_subject_error="yes"),
            "severe subject error rate is not below 5%",
        ),
        (
            lambda rows: rows[33].update(human_making_feasible="fail"),
            "making feasibility is below 85%",
        ),
        (
            lambda rows: rows[2].update(human_advanced_conformance="fail"),
            "advanced creation conformance is below 85%",
        ),
        (
            lambda rows: rows[0].update(material_consistency="fail"),
            "technical data consistency is below 100%",
        ),
    ],
)
def test_release_quality_rejects_every_failed_product_threshold(tmp_path, mutation, message):
    rows = reviewed_rows()
    mutation(rows)
    path = tmp_path / "results.csv"
    write_results(path, rows)

    with pytest.raises(ReleaseQualityError, match=message):
        evaluate(path)


def test_release_quality_rejects_retry_rate_at_fifteen_percent(tmp_path):
    path = tmp_path / "results.csv"
    write_results(path, reviewed_rows())

    with pytest.raises(ReleaseQualityError, match="retry rate is not below 15%"):
        evaluate(path, automatic_retries=15)


def test_management_command_rejects_the_repository_table_while_review_is_pending():
    with pytest.raises(CommandError, match="Human review is incomplete for 40 cases"):
        call_command(
            "check_release_quality",
            generation_attempts=100,
            automatic_retries=0,
            wrong_charges=0,
            open_critical_issues=0,
            deployment_smoke="passed",
        )
