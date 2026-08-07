import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CI_REPORT = PROJECT_ROOT / "docs/ci/github-actions-2026-08-08.json"
EXPECTED_REPOSITORY = "yinqiqi1005-crypto/wo-pin-ge-dou"
REQUIRED_JOBS = {"test", "infrastructure"}


def test_committed_github_actions_evidence_proves_both_jobs_passed():
    report = json.loads(CI_REPORT.read_text(encoding="utf-8"))

    assert report["schema_version"] == 1
    assert report["provider"] == "github-actions"
    assert report["repository"] == EXPECTED_REPOSITORY
    assert report["workflow"] == "test"
    assert report["event"] == "push"
    assert report["branch"] == "main"
    assert report["status"] == "completed"
    assert report["conclusion"] == "success"
    assert re.fullmatch(r"[0-9a-f]{40}", report["commit_sha"])
    assert report["run_id"] > 0
    assert datetime.fromisoformat(report["checked_at"]).tzinfo is not None

    parsed_url = urlparse(report["run_url"])
    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "github.com"
    assert parsed_url.path == (f"/{EXPECTED_REPOSITORY}/actions/runs/{report['run_id']}")

    jobs = {job["name"]: job for job in report["jobs"]}
    assert set(jobs) == REQUIRED_JOBS
    for job in jobs.values():
        assert job["job_id"] > 0
        assert job["status"] == "completed"
        assert job["conclusion"] == "success"
        assert datetime.fromisoformat(job["started_at"]).tzinfo is not None
        assert datetime.fromisoformat(job["completed_at"]).tzinfo is not None
        assert job["verified_steps"]

    assert "pytest: 256 passed" in jobs["test"]["verified_steps"]
    assert "10 concurrent infrastructure round trips" in jobs["infrastructure"]["verified_steps"]
    assert "queued task survives worker restart" in jobs["infrastructure"]["verified_steps"]
