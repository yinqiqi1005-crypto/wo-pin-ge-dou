import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = PROJECT_ROOT / "development-plan.md"
TRACEABILITY_PATH = PROJECT_ROOT / "docs/development-plan-traceability.json"
REQUIREMENT_PATTERN = re.compile(r"M\d-\d{2}")
RANGE_PATTERN = re.compile(r"^(M\d)-(\d{2})(?:\.\.(M\d)-(\d{2}))?$")
PENDING_STATUSES = {
    "target_run_pending",
    "paid_model_review_pending",
    "human_review_pending",
    "public_deployment_pending",
}
MUST_REMAIN_PENDING = {
    "M0-05",
    "M0-06",
    "M0-09",
    "M0-12",
    "M4-03",
    "M5-02",
    "M5-03",
    "M5-04",
    "M7-02",
    "M7-03",
    "M7-04",
    "M9-14",
    "M9-15",
    "M9-17",
    "M9-18",
    "M9-21",
    "M9-22",
    "M9-32",
    "M9-33",
}
EXPECTED_COMPLETION_GATES = {
    "M0-repeatable-target-environment",
    "M1-deterministic-pattern-core",
    "M2-configurable-data-foundation",
    "M3-recorded-internal-demo",
    "M4-real-queue-and-worker",
    "M5-real-multimodal-analysis",
    "M6-first-usability-walkthrough",
    "M7-real-advanced-model-demo",
    "M8-rendered-printable-pdf",
    "M9-human-quality-and-physical-build",
    "M9-public-release",
}


def expand_requirements(value):
    match = RANGE_PATTERN.fullmatch(value)
    assert match is not None, f"Invalid requirement range: {value}"
    start_milestone, start_number, end_milestone, end_number = match.groups()
    if end_milestone is None:
        return [f"{start_milestone}-{start_number}"]
    assert start_milestone == end_milestone, f"Range crosses milestones: {value}"
    start = int(start_number)
    end = int(end_number)
    assert start <= end, f"Range is reversed: {value}"
    return [f"{start_milestone}-{number:02d}" for number in range(start, end + 1)]


def load_traceability():
    return json.loads(TRACEABILITY_PATH.read_text(encoding="utf-8"))


def test_traceability_covers_every_plan_requirement_exactly_once():
    expected = set(REQUIREMENT_PATTERN.findall(PLAN_PATH.read_text(encoding="utf-8")))
    payload = load_traceability()
    expanded = [
        requirement
        for entry in payload["entries"]
        for requirement in expand_requirements(entry["requirements"])
    ]

    assert len(expected) == 222
    assert len(expanded) == len(set(expanded)), "Traceability contains duplicate requirements."
    assert set(expanded) == expected


def test_traceability_evidence_exists_and_pending_work_is_explicit():
    payload = load_traceability()
    allowed_statuses = {"verified_local", *PENDING_STATUSES}
    for entry in payload["entries"]:
        assert entry["status"] in allowed_statuses
        assert entry["evidence"], f"Missing evidence for {entry['requirements']}"
        for evidence in entry["evidence"]:
            path = Path(evidence)
            assert not path.is_absolute(), f"Evidence path must be relative: {evidence}"
            assert (PROJECT_ROOT / path).is_file(), f"Evidence does not exist: {evidence}"
        if entry["status"] == "verified_local":
            assert entry["remaining"] == ""
        else:
            assert entry["remaining"].strip()


def test_external_requirements_cannot_be_marked_as_locally_verified():
    payload = load_traceability()
    status_by_requirement = {
        requirement: entry["status"]
        for entry in payload["entries"]
        for requirement in expand_requirements(entry["requirements"])
    }

    assert all(status_by_requirement[item] in PENDING_STATUSES for item in MUST_REMAIN_PENDING)


def test_unumbered_milestone_completion_gates_are_also_audited():
    payload = load_traceability()
    gates = payload["completion_gates"]
    gate_ids = [gate["gate"] for gate in gates]

    assert len(gate_ids) == len(set(gate_ids))
    assert set(gate_ids) == EXPECTED_COMPLETION_GATES
    for gate in gates:
        assert gate["status"] in {"verified_local", *PENDING_STATUSES}
        assert gate["evidence"]
        for evidence in gate["evidence"]:
            path = Path(evidence)
            assert not path.is_absolute()
            assert (PROJECT_ROOT / path).is_file(), f"Gate evidence does not exist: {evidence}"
        if gate["status"] == "verified_local":
            assert gate["remaining"] == ""
        else:
            assert gate["remaining"].strip()
