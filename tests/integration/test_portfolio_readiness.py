import json

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.operations.models import ConfigurationRevision

pytestmark = pytest.mark.django_db


@pytest.fixture
def prepared_demo(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_demo_config", verbosity=0)
    call_command("prepare_demo", password="Portfolio-Demo-2026", verbosity=0)


def test_portfolio_demo_check_proves_offline_showcase_is_ready(prepared_demo, tmp_path):
    report_path = tmp_path / "portfolio.json"

    call_command("check_portfolio_demo", report=report_path, verbosity=0)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["result"] == "passed"
    assert report["profile"] == "local-offline-portfolio"
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
    assert len(report["generated_patterns"]) == 3
    assert all(item["grid_size"] == 30 for item in report["generated_patterns"])
    assert all(0 < item["color_count"] <= 12 for item in report["generated_patterns"])
    assert report["page_checks"] == {"/": 200, "/accounts/login/": 200, "/health/": 200}


def test_portfolio_demo_check_rejects_non_offline_analysis_route(prepared_demo):
    route = ConfigurationRevision.objects.get(
        namespace="model_routes",
        key="analysis",
        version=1,
    )
    route.value = {**route.value, "provider": "openai"}
    route.save(update_fields=("value",))

    with pytest.raises(CommandError, match="must use rules"):
        call_command("check_portfolio_demo", verbosity=0)


def test_portfolio_demo_check_rejects_corrupt_demo_image(prepared_demo):
    path = "demo-assets/demo-person.png"
    default_storage.delete(path)
    default_storage.save(path, ContentFile(b"not-an-image"))

    with pytest.raises(CommandError, match="cannot generate a pattern"):
        call_command("check_portfolio_demo", verbosity=0)


def test_portfolio_demo_check_rejects_disabled_media_previews(prepared_demo, settings):
    settings.SERVE_MEDIA = False

    with pytest.raises(CommandError, match="must serve uploaded media previews"):
        call_command("check_portfolio_demo", verbosity=0)
