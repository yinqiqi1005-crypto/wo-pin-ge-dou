import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from django.core.management.base import CommandError

from apps.operations.management.commands.probe_ai_service import Command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_REPORT = PROJECT_ROOT / "docs/model-evaluations/service-capability-2026-08-08.json"
FORBIDDEN_KEYS = {"api_key", "base_url", "host", "password", "secret"}


def service_settings(*, api_key="configured", base_url="https://api.deepseek.com"):
    return patch(
        "apps.operations.management.commands.probe_ai_service.settings",
        SimpleNamespace(OPENAI_API_KEY=api_key, OPENAI_BASE_URL=base_url),
    )


def model_client(*model_ids):
    client = Mock()
    client.models.list.return_value = SimpleNamespace(
        data=[SimpleNamespace(id=model_id) for model_id in model_ids]
    )
    return client


def test_probe_records_text_only_service_without_billable_calls(tmp_path):
    report_path = tmp_path / "service-capability.json"
    client = model_client("deepseek-v4-pro", "deepseek-v4-flash")
    command = Command()

    with service_settings(), patch.object(command, "_build_client", return_value=client):
        command.handle(report=str(report_path))

    client.models.list.assert_called_once_with()
    assert client.method_calls == [call.models.list()]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["result"] == "insufficient"
    assert report["provider"] == "deepseek"
    assert report["available_models"] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert report["capabilities"] == {"image_analysis": False, "image_edit": False}
    assert report["required_capabilities_available"] is False
    assert report["request_scope"] == {
        "billable_generation_calls": 0,
        "images_uploaded": 0,
        "models_list_calls": 1,
    }


def test_probe_refuses_to_overwrite_previous_evidence(tmp_path):
    report_path = tmp_path / "service-capability.json"
    report_path.write_text("previous evidence\n", encoding="utf-8")
    command = Command()
    with (
        service_settings(),
        patch.object(command, "_build_client", return_value=model_client("deepseek-v4-pro")),
        pytest.raises(CommandError, match="Cannot create AI service capability evidence"),
    ):
        command.handle(report=str(report_path))
    assert report_path.read_text(encoding="utf-8") == "previous evidence\n"


@pytest.mark.parametrize(
    ("api_key", "service_url", "message"),
    [
        ("", "https://api.deepseek.com", "OPENAI_API_KEY is required"),
        ("configured", "https://private.example.invalid", "no audited capability profile"),
    ],
)
def test_probe_refuses_missing_credentials_or_unknown_providers(
    tmp_path,
    api_key,
    service_url,
    message,
):
    with (
        service_settings(api_key=api_key, base_url=service_url),
        pytest.raises(CommandError, match=message),
    ):
        Command().handle(report=str(tmp_path / "report.json"))


def test_probe_refuses_to_guess_capability_for_unknown_models(tmp_path):
    command = Command()
    with (
        service_settings(),
        patch.object(command, "_build_client", return_value=model_client("deepseek-future")),
        pytest.raises(CommandError, match="outside the audited profile"),
    ):
        command.handle(report=str(tmp_path / "report.json"))


def test_committed_service_probe_proves_current_provider_is_text_only_without_spend():
    report = json.loads(COMMITTED_REPORT.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["result"] == "insufficient"
    assert report["provider"] == "deepseek"
    assert report["available_models"] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert report["capabilities"] == {"image_analysis": False, "image_edit": False}
    assert report["required_capabilities_available"] is False
    assert report["request_scope"] == {
        "billable_generation_calls": 0,
        "images_uploaded": 0,
        "models_list_calls": 1,
    }
    assert len(report["official_sources"]) >= 2
    assert all(
        source.startswith("https://api-docs.deepseek.com/") for source in report["official_sources"]
    )
    assert FORBIDDEN_KEYS.isdisjoint(report)
