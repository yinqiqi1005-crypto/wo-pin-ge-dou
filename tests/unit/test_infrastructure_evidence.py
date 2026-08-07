import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INFRASTRUCTURE_REPORT = PROJECT_ROOT / "docs/infrastructure/local-2026-08-08.json"
RECOVERY_REPORT = PROJECT_ROOT / "docs/infrastructure/worker-recovery-2026-08-08.json"
FORBIDDEN_KEYS = {"address", "api_key", "host", "password", "secret", "url"}


def load_report(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_common_report_fields(report):
    assert report["schema_version"] == 1
    assert report["result"] == "passed"
    checked_at = datetime.fromisoformat(report["checked_at"])
    assert checked_at.tzinfo is not None

    def walk(value):
        if isinstance(value, dict):
            assert FORBIDDEN_KEYS.isdisjoint(value)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(report)


def test_committed_target_infrastructure_evidence_proves_real_versions_and_concurrency():
    report = load_report(INFRASTRUCTURE_REPORT)
    assert_common_report_fields(report)
    assert report["check"] == "target-infrastructure"
    assert report["database"]["engine"] == "postgresql"
    assert report["database"]["version"].split(".", 1)[0] == "16"
    assert report["redis"]["version"].split(".", 1)[0] == "7"
    assert report["celery"]["always_eager"] is False
    assert report["celery"]["concurrent_round_trips"] >= 10
    assert report["admin"]["required"] is True
    assert report["admin"]["active_superuser_count"] >= 1


def test_committed_worker_recovery_evidence_proves_offline_queue_and_same_result():
    report = load_report(RECOVERY_REPORT)
    assert_common_report_fields(report)
    assert report["check"] == "worker-restart-recovery"
    assert report["database"]["engine"] == "postgresql"
    assert report["celery"]["always_eager"] is False
    assert report["celery"]["queued_while_worker_offline"] is True
    assert report["celery"]["same_task_result_verified"] is True
    assert report["task_id"]
