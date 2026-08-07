import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from apps.operations.release_evidence import (
    ReleaseEvidenceError,
    count_open_critical_issues,
    validate_deployment_report,
)

ISSUE_FIELDS = ("issue_id", "severity", "status", "title")


def write_issues(path, rows):
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def deployment_payload(checked_at):
    return {
        "checked_at": checked_at.isoformat(),
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


def write_deployment(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_issue_register_counts_only_open_p0_and_p1(tmp_path):
    path = tmp_path / "issues.csv"
    write_issues(
        path,
        [
            {"issue_id": "BUG-1", "severity": "P0", "status": "open", "title": "A"},
            {"issue_id": "BUG-2", "severity": "P1", "status": "closed", "title": "B"},
            {"issue_id": "BUG-3", "severity": "P2", "status": "open", "title": "C"},
        ],
    )

    assert count_open_critical_issues(path) == 1


def test_empty_issue_register_is_valid(tmp_path):
    path = tmp_path / "issues.csv"
    write_issues(path, [])

    assert count_open_critical_issues(path) == 0


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [
                {"issue_id": "BUG-1", "severity": "P1", "status": "open", "title": "A"},
                {"issue_id": "BUG-1", "severity": "P2", "status": "closed", "title": "B"},
            ],
            "IDs must be unique",
        ),
        (
            [{"issue_id": "BUG-1", "severity": "urgent", "status": "open", "title": "A"}],
            "Invalid issue severity",
        ),
        (
            [{"issue_id": "BUG-1", "severity": "P1", "status": "fixed", "title": "A"}],
            "Invalid issue status",
        ),
        (
            [{"issue_id": "BUG-1", "severity": "P1", "status": "open", "title": " "}],
            "requires a title",
        ),
        (
            [{"issue_id": "", "severity": "P1", "status": "open", "title": "A"}],
            "requires an issue_id",
        ),
    ],
)
def test_issue_register_rejects_unreliable_rows(tmp_path, rows, message):
    path = tmp_path / "issues.csv"
    write_issues(path, rows)

    with pytest.raises(ReleaseEvidenceError, match=message):
        count_open_critical_issues(path)


def test_deployment_report_accepts_recent_public_https_evidence(tmp_path):
    now = datetime(2026, 8, 8, 10, tzinfo=UTC)
    path = tmp_path / "deployment.json"
    write_deployment(path, deployment_payload(now - timedelta(days=6)))

    payload = validate_deployment_report(path, now=now)

    assert payload["base_url"] == "https://beads.example/"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.update(
                base_url="http://localhost:8000/",
                health_url="http://localhost:8000/health/",
                homepage_url="http://localhost:8000/",
                css_url="http://localhost:8000/static/css/app.0123456789ab.css",
                javascript_url="http://localhost:8000/static/js/creation.0123456789ab.js",
            ),
            "only HTTPS URLs",
        ),
        (
            lambda payload: payload.update(health_url="https://other.example/health/"),
            "same host",
        ),
        (
            lambda payload: payload["checks"].update(hsts="skipped_for_local_http"),
            "does not pass every required check",
        ),
    ],
)
def test_deployment_report_rejects_non_public_or_failed_evidence(tmp_path, mutate, message):
    now = datetime(2026, 8, 8, 10, tzinfo=UTC)
    payload = deployment_payload(now)
    mutate(payload)
    path = tmp_path / "deployment.json"
    write_deployment(path, payload)

    with pytest.raises(ReleaseEvidenceError, match=message):
        validate_deployment_report(path, now=now)


@pytest.mark.parametrize("offset", [timedelta(days=-8), timedelta(seconds=1)])
def test_deployment_report_rejects_stale_or_future_evidence(tmp_path, offset):
    now = datetime(2026, 8, 8, 10, tzinfo=UTC)
    path = tmp_path / "deployment.json"
    write_deployment(path, deployment_payload(now + offset))

    with pytest.raises(ReleaseEvidenceError, match="last 7 days"):
        validate_deployment_report(path, now=now)


def test_deployment_report_rejects_invalid_json(tmp_path):
    path = tmp_path / "deployment.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="not valid JSON"):
        validate_deployment_report(path)
