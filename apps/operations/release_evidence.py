import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from apps.creation.models import GenerationStatus, GenerationTask
from apps.memberships.models import (
    GenerationQuotaLedger,
    GenerationQuotaPeriod,
    QuotaLedgerEvent,
)


class ReleaseEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class OperationalMetrics:
    generation_attempts: int
    retried_tasks: int
    wrong_charge_count: int
    unfinished_task_count: int

    @property
    def automatic_retry_rate(self):
        if self.generation_attempts == 0:
            return 0.0
        return self.retried_tasks / self.generation_attempts


TERMINAL_STATUSES = {
    GenerationStatus.SUCCEEDED,
    GenerationStatus.SAVED,
    GenerationStatus.FAILED,
    GenerationStatus.CANCELLED,
}
ACTIVE_GENERATION_STATUSES = {
    GenerationStatus.QUOTA_RESERVED,
    GenerationStatus.QUEUED,
    GenerationStatus.GENERATING,
    GenerationStatus.VALIDATING,
}
SUCCESS_STATUSES = {GenerationStatus.SUCCEEDED, GenerationStatus.SAVED}
CHARGE_EVENTS = {
    QuotaLedgerEvent.RESERVE,
    QuotaLedgerEvent.CONSUME,
    QuotaLedgerEvent.RELEASE,
}


def collect_operational_metrics():
    tasks = list(GenerationTask.objects.values("id", "status", "started_at", "retry_count"))
    task_ids = {task["id"] for task in tasks}
    events_by_task = defaultdict(lambda: defaultdict(int))
    wrong_charge_count = 0
    charge_rows = GenerationQuotaLedger.objects.filter(event__in=CHARGE_EVENTS).values(
        "task_reference",
        "quota_period_id",
        "event",
        "amount",
    )
    period_event_totals = defaultdict(lambda: defaultdict(int))
    for row in charge_rows:
        reference = row["task_reference"]
        event = row["event"]
        amount = row["amount"]
        period_event_totals[row["quota_period_id"]][event] += amount
        if reference not in task_ids:
            wrong_charge_count += 1
            continue
        events_by_task[reference][event] += amount
        if amount != 1:
            wrong_charge_count += 1

    for task in tasks:
        events = events_by_task[task["id"]]
        reserved = events[QuotaLedgerEvent.RESERVE]
        consumed = events[QuotaLedgerEvent.CONSUME]
        released = events[QuotaLedgerEvent.RELEASE]
        if consumed and released:
            wrong_charge_count += 1
        if task["status"] in SUCCESS_STATUSES:
            if (reserved, consumed, released) != (1, 1, 0):
                wrong_charge_count += 1
        elif task["status"] in {GenerationStatus.FAILED, GenerationStatus.CANCELLED}:
            if reserved and (reserved, consumed, released) != (1, 0, 1):
                wrong_charge_count += 1
            if not reserved and (consumed or released):
                wrong_charge_count += 1
        elif consumed or released:
            wrong_charge_count += 1

    for period in GenerationQuotaPeriod.objects.values("id", "used_count", "reserved_count"):
        totals = period_event_totals[period["id"]]
        expected_used = totals[QuotaLedgerEvent.CONSUME]
        expected_reserved = (
            totals[QuotaLedgerEvent.RESERVE]
            - totals[QuotaLedgerEvent.CONSUME]
            - totals[QuotaLedgerEvent.RELEASE]
        )
        if period["used_count"] != expected_used or period["reserved_count"] != expected_reserved:
            wrong_charge_count += 1

    started_tasks = [task for task in tasks if task["started_at"] is not None]
    return OperationalMetrics(
        generation_attempts=len(started_tasks),
        retried_tasks=sum(task["retry_count"] > 0 for task in started_tasks),
        wrong_charge_count=wrong_charge_count,
        unfinished_task_count=sum(
            task["status"] in ACTIVE_GENERATION_STATUSES
            or (task["started_at"] is not None and task["status"] not in TERMINAL_STATUSES)
            for task in tasks
        ),
    )


def count_open_critical_issues(path):
    with Path(path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        required = {"issue_id", "severity", "status", "title"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ReleaseEvidenceError(
                "Issue register is missing columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)
    if len({row["issue_id"] for row in rows}) != len(rows):
        raise ReleaseEvidenceError("Issue register IDs must be unique.")
    for row in rows:
        if not row["issue_id"].strip():
            raise ReleaseEvidenceError("Every issue requires an issue_id.")
        if row["severity"] not in {"P0", "P1", "P2", "P3"}:
            raise ReleaseEvidenceError(f"Invalid issue severity: {row['severity']}")
        if row["status"] not in {"open", "closed"}:
            raise ReleaseEvidenceError(f"Invalid issue status: {row['status']}")
        if not row["title"].strip():
            raise ReleaseEvidenceError(f"Issue {row['issue_id']} requires a title.")
    return sum(row["severity"] in {"P0", "P1"} and row["status"] == "open" for row in rows)


def validate_deployment_report(path, *, now=None, maximum_age=timedelta(days=7)):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReleaseEvidenceError("Deployment report is not valid JSON.") from exc
    required = {
        "checked_at",
        "base_url",
        "health_url",
        "homepage_url",
        "css_url",
        "javascript_url",
        "checks",
    }
    missing = required - set(payload)
    if missing:
        raise ReleaseEvidenceError(
            "Deployment report is missing fields: " + ", ".join(sorted(missing))
        )
    urls = [
        payload["base_url"],
        payload["health_url"],
        payload["homepage_url"],
        payload["css_url"],
        payload["javascript_url"],
    ]
    parsed = [urlparse(url) for url in urls]
    if any(url.scheme != "https" or not url.hostname for url in parsed):
        raise ReleaseEvidenceError("Deployment report must contain only HTTPS URLs.")
    if len({url.hostname for url in parsed}) != 1:
        raise ReleaseEvidenceError("Deployment report URLs must use the same host.")
    required_checks = {
        "health",
        "homepage",
        "fingerprinted_assets",
        "content_type_nosniff",
        "frame_options_deny",
        "referrer_policy",
        "hsts",
    }
    checks = payload["checks"]
    if not isinstance(checks, dict) or any(
        checks.get(name) is not True for name in required_checks
    ):
        raise ReleaseEvidenceError("Deployment report does not pass every required check.")
    try:
        checked_at = datetime.fromisoformat(payload["checked_at"])
    except (TypeError, ValueError) as exc:
        raise ReleaseEvidenceError("Deployment report checked_at is invalid.") from exc
    if checked_at.tzinfo is None:
        raise ReleaseEvidenceError("Deployment report checked_at must include a timezone.")
    current = now or datetime.now(UTC)
    if checked_at > current or current - checked_at > maximum_age:
        raise ReleaseEvidenceError("Deployment report must be from the last 7 days.")
    return payload
