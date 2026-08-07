import csv
import json
from datetime import UTC, date, datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from PIL import Image

from apps.creation.models import GenerationStatus, GenerationTask
from apps.memberships.models import (
    GenerationQuotaLedger,
    GenerationQuotaPeriod,
    MembershipLevel,
    MembershipPlan,
    QuotaLedgerEvent,
    QuotaPeriodType,
)
from apps.operations.release_evidence import OperationalMetrics
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
PHYSICAL_FIELDS = (
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
USABILITY_FIELDS = (
    "session_id",
    "tester_alias",
    "participant_type",
    "session_date",
    "device",
    "task_id",
    "completion_status",
    "assistance_count",
    "completion_seconds",
    "confusion_severity",
    "observation",
    "reviewer",
    "status",
)
USABILITY_TASKS = (
    "upload-and-feedback",
    "confirm-subject",
    "choose-settings",
    "generate-and-recover",
    "inspect-pattern",
    "save-and-find",
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


def write_complete_physical_results(path):
    rows = []
    photo_dir = path.parent / "physical-photos"
    photo_dir.mkdir(exist_ok=True)
    for case_id, category in (("per-01", "person"), ("pet-01", "pet"), ("obj-01", "object")):
        photo_path = photo_dir / f"{case_id}.png"
        Image.new("RGB", (24, 24), (170, 90, 60)).save(photo_path)
        rows.append(
            {
                "case_id": case_id,
                "category": category,
                "grid_size": 30,
                "planned_beads": 900,
                "actual_beads": 900,
                "bead_difference": 0,
                "color_substitutions": "无",
                "making_minutes": 75,
                "ironing_result": "pass",
                "finished_photo": f"physical-photos/{case_id}.png",
                "reviewer": "测试评审人",
                "review_date": date.today().isoformat(),
                "status": "complete",
                "notes": "通过",
            }
        )
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=PHYSICAL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_valid_deployment_report(path):
    payload = {
        "checked_at": datetime.now(UTC).isoformat(),
        "base_url": "https://beads.example/",
        "health_url": "https://beads.example/health/",
        "homepage_url": "https://beads.example/",
        "css_url": "https://beads.example/static/css/app.0123456789ab.css",
        "javascript_url": "https://beads.example/static/js/creation.0123456789ab.js",
        "checks": {
            "health": True,
            "homepage": True,
            "fingerprinted_assets": True,
            "content_type_nosniff": True,
            "frame_options_deny": True,
            "referrer_policy": True,
            "hsts": True,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_complete_usability_results(path):
    rows = [
        {
            "session_id": "release-session",
            "tester_alias": "external-tester-01",
            "participant_type": "external_human",
            "session_date": date.today().isoformat(),
            "device": "desktop",
            "task_id": task_id,
            "completion_status": "completed",
            "assistance_count": 0,
            "completion_seconds": 45,
            "confusion_severity": "none",
            "observation": "测试者独立完成任务。",
            "reviewer": "moderator-01",
            "status": "complete",
        }
        for task_id in USABILITY_TASKS
    ]
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=USABILITY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(path, **overrides):
    physical_path = overrides.pop("physical_results_path", path.parent / "physical.csv")
    if not physical_path.exists():
        write_complete_physical_results(physical_path)
    deployment_path = overrides.pop(
        "deployment_report_path",
        path.parent / "deployment.json",
    )
    if not deployment_path.exists():
        write_valid_deployment_report(deployment_path)
    usability_path = overrides.pop(
        "usability_results_path",
        path.parent / "usability.csv",
    )
    if not usability_path.exists():
        write_complete_usability_results(usability_path)
    arguments = {
        "operational_metrics": OperationalMetrics(
            generation_attempts=100,
            retried_tasks=14,
            wrong_charge_count=0,
            unfinished_task_count=0,
        ),
        "open_critical_issues": 0,
        "deployment_report_path": deployment_path,
        "physical_results_path": physical_path,
        "usability_results_path": usability_path,
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
    assert summary.physical_case_count == 3
    assert summary.usability_task_count == 6


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
        evaluate(
            path,
            operational_metrics=OperationalMetrics(100, 15, 0, 0),
        )


@pytest.mark.parametrize(
    ("metrics", "message"),
    [
        (OperationalMetrics(0, 0, 0, 0), "No generation attempts"),
        (OperationalMetrics(100, 0, 1, 0), "incorrect image charges"),
        (OperationalMetrics(100, 0, 0, 1), "tasks remain unfinished"),
    ],
)
def test_release_quality_rejects_invalid_database_operational_evidence(
    tmp_path,
    metrics,
    message,
):
    path = tmp_path / "results.csv"
    write_results(path, reviewed_rows())

    with pytest.raises(ReleaseQualityError, match=message):
        evaluate(path, operational_metrics=metrics)


def test_release_quality_rejects_local_deployment_report(tmp_path):
    path = tmp_path / "results.csv"
    write_results(path, reviewed_rows())
    deployment_path = tmp_path / "deployment.json"
    write_valid_deployment_report(deployment_path)
    payload = json.loads(deployment_path.read_text(encoding="utf-8"))
    for field in ("base_url", "health_url", "homepage_url", "css_url", "javascript_url"):
        payload[field] = payload[field].replace("https://beads.example", "http://localhost:8000")
    deployment_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseQualityError, match="only HTTPS URLs"):
        evaluate(path, deployment_report_path=deployment_path)


def test_release_quality_rejects_pending_physical_builds_even_after_40_reviews(tmp_path):
    path = tmp_path / "results.csv"
    write_results(path, reviewed_rows())
    physical_path = tmp_path / "physical.csv"
    write_complete_physical_results(physical_path)
    with physical_path.open(encoding="utf-8", newline="") as source:
        physical_rows = list(csv.DictReader(source))
    physical_rows[0]["status"] = "pending"
    with physical_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=PHYSICAL_FIELDS)
        writer.writeheader()
        writer.writerows(physical_rows)

    with pytest.raises(ReleaseQualityError, match="Physical validation is incomplete"):
        evaluate(path, physical_results_path=physical_path)


def test_release_quality_rejects_pending_usability_walkthrough(tmp_path):
    path = tmp_path / "results.csv"
    write_results(path, reviewed_rows())
    usability_path = tmp_path / "usability.csv"
    write_complete_usability_results(usability_path)
    with usability_path.open(encoding="utf-8", newline="") as source:
        usability_rows = list(csv.DictReader(source))
    usability_rows[0]["status"] = "pending"
    with usability_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=USABILITY_FIELDS)
        writer.writeheader()
        writer.writerows(usability_rows)

    with pytest.raises(ReleaseQualityError, match="Usability walkthrough is incomplete"):
        evaluate(path, usability_results_path=usability_path)


@pytest.mark.django_db
def test_management_command_rejects_the_repository_table_while_review_is_pending(tmp_path):
    with pytest.raises(CommandError, match="Human review is incomplete for 40 cases"):
        call_command(
            "check_release_quality",
            deployment_report=tmp_path / "not-reached.json",
        )


@pytest.mark.django_db
def test_management_command_passes_only_with_database_and_file_evidence(
    tmp_path,
    django_user_model,
    capsys,
):
    results_path = tmp_path / "results.csv"
    physical_path = tmp_path / "physical.csv"
    deployment_path = tmp_path / "deployment.json"
    usability_path = tmp_path / "usability.csv"
    issues_path = tmp_path / "issues.csv"
    write_results(results_path, reviewed_rows())
    write_complete_physical_results(physical_path)
    write_valid_deployment_report(deployment_path)
    write_complete_usability_results(usability_path)
    issues_path.write_text("issue_id,severity,status,title\n", encoding="utf-8")

    user = django_user_model.objects.create_user(username="release-command-user")
    plan = MembershipPlan.objects.create(
        level=MembershipLevel.REGISTERED,
        name="Registered",
        quota_period=QuotaPeriodType.MONTHLY,
        generation_limit=10,
    )
    quota = GenerationQuotaPeriod.objects.create(
        user=user,
        plan=plan,
        starts_at=timezone.now(),
        total_limit=10,
        used_count=1,
    )
    task = GenerationTask.objects.create(
        user=user,
        quota_period=quota,
        status=GenerationStatus.SUCCEEDED,
        idempotency_key="release-command-task",
        started_at=timezone.now(),
        completed_at=timezone.now(),
    )
    for event in (QuotaLedgerEvent.RESERVE, QuotaLedgerEvent.CONSUME):
        GenerationQuotaLedger.objects.create(
            quota_period=quota,
            task_reference=task.id,
            event=event,
            amount=1,
            idempotency_key=f"release-command-{event}",
        )

    call_command(
        "check_release_quality",
        results=results_path,
        physical_results=physical_path,
        usability_results=usability_path,
        issues=issues_path,
        deployment_report=deployment_path,
    )

    assert "Release quality passed" in capsys.readouterr().out
