import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


class UsabilityWalkthroughError(ValueError):
    pass


REQUIRED_TASKS = {
    "upload-and-feedback",
    "confirm-subject",
    "choose-settings",
    "generate-and-recover",
    "inspect-pattern",
    "save-and-find",
}
REQUIRED_COLUMNS = {
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
}
ALLOWED_DEVICES = {"desktop", "mobile"}
ALLOWED_COMPLETION = {"completed", "completed_with_help"}
ALLOWED_CONFUSION = {"none", "minor"}


@dataclass(frozen=True)
class UsabilityWalkthroughSummary:
    task_count: int
    total_seconds: int
    total_assistance_count: int
    device: str


def _positive_integer(row, field, *, allow_zero=False):
    try:
        value = int(row[field])
    except (TypeError, ValueError) as exc:
        raise UsabilityWalkthroughError(
            f"{row.get('task_id', 'unknown')} has invalid {field}."
        ) from exc
    if value < 0 or (value == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise UsabilityWalkthroughError(
            f"{row.get('task_id', 'unknown')} requires {qualifier} {field}."
        )
    return value


def evaluate_usability_walkthrough(results_path):
    path = Path(results_path)
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise UsabilityWalkthroughError(
                "Usability walkthrough is missing columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)

    task_ids = [row["task_id"] for row in rows]
    if len(rows) != len(REQUIRED_TASKS) or set(task_ids) != REQUIRED_TASKS:
        raise UsabilityWalkthroughError(
            "Usability walkthrough requires each of the six fixed tasks exactly once."
        )
    if len(task_ids) != len(set(task_ids)):
        raise UsabilityWalkthroughError("Usability task_id values must be unique.")
    pending = [row["task_id"] for row in rows if row["status"] != "complete"]
    if pending:
        raise UsabilityWalkthroughError(
            "Usability walkthrough is incomplete for: " + ", ".join(pending)
        )

    session_ids = {row["session_id"].strip() for row in rows}
    tester_aliases = {row["tester_alias"].strip() for row in rows}
    session_dates = {row["session_date"].strip() for row in rows}
    devices = {row["device"] for row in rows}
    reviewers = {row["reviewer"].strip() for row in rows}
    if len(session_ids) != 1 or "" in session_ids:
        raise UsabilityWalkthroughError("All usability tasks require one non-empty session_id.")
    if len(tester_aliases) != 1 or "" in tester_aliases:
        raise UsabilityWalkthroughError("All usability tasks require one tester alias.")
    if any(row["participant_type"] != "external_human" for row in rows):
        raise UsabilityWalkthroughError("Usability participant must be an external human tester.")
    if len(session_dates) != 1:
        raise UsabilityWalkthroughError("All usability tasks must share one session_date.")
    try:
        reviewed_on = date.fromisoformat(next(iter(session_dates)))
    except ValueError as exc:
        raise UsabilityWalkthroughError(
            "Usability walkthrough requires an ISO session_date."
        ) from exc
    if not date.today() - timedelta(days=90) <= reviewed_on <= date.today():
        raise UsabilityWalkthroughError(
            "Usability session_date must be within the last 90 days and not in the future."
        )
    if len(devices) != 1 or not devices.issubset(ALLOWED_DEVICES):
        raise UsabilityWalkthroughError("All usability tasks require one valid device type.")
    if len(reviewers) != 1 or "" in reviewers:
        raise UsabilityWalkthroughError("All usability tasks require one reviewer.")

    total_seconds = 0
    total_assistance = 0
    for row in rows:
        if row["completion_status"] not in ALLOWED_COMPLETION:
            raise UsabilityWalkthroughError(f"{row['task_id']} was not completed by the tester.")
        if row["confusion_severity"] not in ALLOWED_CONFUSION:
            raise UsabilityWalkthroughError(
                f"{row['task_id']} has unresolved major or critical confusion."
            )
        if not row["observation"].strip():
            raise UsabilityWalkthroughError(f"{row['task_id']} requires an observation.")
        total_assistance += _positive_integer(row, "assistance_count", allow_zero=True)
        total_seconds += _positive_integer(row, "completion_seconds")

    return UsabilityWalkthroughSummary(
        task_count=len(rows),
        total_seconds=total_seconds,
        total_assistance_count=total_assistance,
        device=next(iter(devices)),
    )
