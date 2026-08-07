import csv
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.core.management.base import CommandError

from apps.operations.management.commands.check_usability_walkthrough import Command
from apps.operations.usability_walkthrough import (
    UsabilityWalkthroughError,
    evaluate_usability_walkthrough,
)

FIELDS = (
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
TASKS = (
    "upload-and-feedback",
    "confirm-subject",
    "choose-settings",
    "generate-and-recover",
    "inspect-pattern",
    "save-and-find",
)
REPOSITORY_TEMPLATE = Path(__file__).parents[2] / "docs/usability-walkthrough.csv"


def complete_rows():
    return [
        {
            "session_id": "session-2026-08",
            "tester_alias": "tester-01",
            "participant_type": "external_human",
            "session_date": date.today().isoformat(),
            "device": "desktop",
            "task_id": task_id,
            "completion_status": "completed" if index != 3 else "completed_with_help",
            "assistance_count": 0 if index != 3 else 1,
            "completion_seconds": 30 + index * 10,
            "confusion_severity": "none" if index != 3 else "minor",
            "observation": "测试者完成任务并说明了页面反馈。",
            "reviewer": "moderator-01",
            "status": "complete",
        }
        for index, task_id in enumerate(TASKS)
    ]


def write_results(path, rows):
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_complete_external_human_walkthrough_passes(tmp_path):
    path = tmp_path / "usability.csv"
    write_results(path, complete_rows())

    summary = evaluate_usability_walkthrough(path)

    assert summary.task_count == 6
    assert summary.total_seconds == 330
    assert summary.total_assistance_count == 1
    assert summary.device == "desktop"


def test_repository_walkthrough_template_is_intentionally_pending():
    with pytest.raises(UsabilityWalkthroughError, match="incomplete for"):
        evaluate_usability_walkthrough(REPOSITORY_TEMPLATE)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows[0].update(participant_type="project_member"), "external human"),
        (lambda rows: rows[0].update(completion_status="blocked"), "not completed"),
        (lambda rows: rows[0].update(confusion_severity="major"), "unresolved major"),
        (lambda rows: rows[0].update(observation=""), "requires an observation"),
        (lambda rows: rows[0].update(assistance_count=-1), "non-negative assistance_count"),
        (
            lambda rows: [
                row.update(session_date=(date.today() - timedelta(days=91)).isoformat())
                for row in rows
            ],
            "within the last 90 days",
        ),
    ],
)
def test_walkthrough_rejects_unverified_or_unsuccessful_human_evidence(
    tmp_path,
    mutation,
    message,
):
    rows = complete_rows()
    mutation(rows)
    path = tmp_path / "usability.csv"
    write_results(path, rows)

    with pytest.raises(UsabilityWalkthroughError, match=message):
        evaluate_usability_walkthrough(path)


def test_walkthrough_requires_each_fixed_task_exactly_once(tmp_path):
    rows = complete_rows()
    rows[-1]["task_id"] = rows[0]["task_id"]
    path = tmp_path / "usability.csv"
    write_results(path, rows)

    with pytest.raises(UsabilityWalkthroughError, match="six fixed tasks exactly once"):
        evaluate_usability_walkthrough(path)


def test_command_writes_non_overwritable_walkthrough_evidence(tmp_path):
    results_path = tmp_path / "usability.csv"
    report_path = tmp_path / "usability.json"
    write_results(results_path, complete_rows())

    Command().handle(results=str(results_path), report=str(report_path))

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "passed"
    assert report["participant_type"] == "external_human"
    assert report["task_count"] == 6
    assert report["total_assistance_count"] == 1

    with pytest.raises(CommandError, match="Cannot create usability walkthrough evidence"):
        Command().handle(results=str(results_path), report=str(report_path))
