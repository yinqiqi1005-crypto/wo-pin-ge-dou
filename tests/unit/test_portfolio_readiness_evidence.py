import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "docs/portfolio-readiness/local-2026-08-08.json"


def test_committed_portfolio_readiness_evidence_proves_local_demo_is_presentable():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["schema_version"] == 1
    assert report["check"] == "portfolio-demo-readiness"
    assert report["profile"] == "local-offline-portfolio"
    assert report["result"] == "passed"
    assert datetime.fromisoformat(report["checked_at"]).tzinfo is not None
    assert report["portfolio_demo_requires_external_validation"] is False
    assert report["production_validation_status"] == "not_evaluated"
    assert report["media_serving_enabled"] is True
    assert report["membership_levels"] == ["plus", "pro", "registered", "visitor"]
    assert report["demo_accounts"] == {
        "demo_plus": "plus",
        "demo_pro": "pro",
        "demo_registered": "registered",
    }
    assert report["model_routes"] == {
        "advanced_creation": "mock",
        "analysis": "rules",
    }
    assert report["page_checks"] == {"/": 200, "/accounts/login/": 200, "/health/": 200}
    assert len(report["generated_patterns"]) == 3
    assert {item["asset"] for item in report["generated_patterns"]} == {
        "demo-assets/demo-person.png",
        "demo-assets/demo-pet.png",
        "demo-assets/demo-object.png",
    }
    assert all(item["grid_size"] == 30 for item in report["generated_patterns"])
    assert all(0 < item["color_count"] <= 12 for item in report["generated_patterns"])
    assert all(item["total_beads"] == 900 for item in report["generated_patterns"])
