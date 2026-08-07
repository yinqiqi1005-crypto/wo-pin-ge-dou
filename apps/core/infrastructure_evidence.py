import json
from datetime import UTC, datetime
from pathlib import Path


class EvidenceWriteError(RuntimeError):
    pass


def write_evidence(path, payload):
    if not path:
        return

    report_path = Path(path)
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        **payload,
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("x", encoding="utf-8") as report_file:
            json.dump(report, report_file, ensure_ascii=False, indent=2, sort_keys=True)
            report_file.write("\n")
    except OSError as exc:
        raise EvidenceWriteError(f"Cannot create infrastructure evidence: {exc}") from exc
