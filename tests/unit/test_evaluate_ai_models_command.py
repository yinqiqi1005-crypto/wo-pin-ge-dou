import csv
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from PIL import Image

from apps.operations.management.commands.evaluate_ai_models import Command


def make_images(directory, count=10):
    directory.mkdir()
    for index in range(count):
        Image.new("RGB", (32, 32), (80 + index, 120, 160)).save(
            directory / f"image-{index:02d}.png"
        )


def command_options(image_dir, output_dir, **overrides):
    options = {
        "capability": "analysis",
        "models": ["vision-a", "vision-b"],
        "image_dir": str(image_dir),
        "output_dir": str(output_dir),
        "run_id": "evaluation-01",
        "confirm_billable": True,
    }
    options.update(overrides)
    return options


@override_settings(OPENAI_API_KEY="test-only-key")
def test_evaluation_refuses_to_touch_provider_without_explicit_billable_confirmation(tmp_path):
    image_dir = tmp_path / "images"
    make_images(image_dir)

    with (
        patch.object(Command, "_build_client") as build_client,
        pytest.raises(CommandError, match="without --confirm-billable"),
    ):
        call_command(
            "evaluate_ai_models",
            **command_options(
                image_dir,
                tmp_path / "output",
                confirm_billable=False,
            ),
        )

    build_client.assert_not_called()


@pytest.mark.parametrize("models", [["only-one"], ["a", "b", "c", "d"], ["a", "a"]])
@override_settings(OPENAI_API_KEY="test-only-key")
def test_evaluation_requires_two_or_three_unique_models(tmp_path, models):
    image_dir = tmp_path / "images"
    make_images(image_dir)

    with pytest.raises(CommandError, match="2 or 3 unique"):
        call_command(
            "evaluate_ai_models",
            **command_options(tmp_path / "images", tmp_path / "output", models=models),
        )


@pytest.mark.parametrize(
    ("run_id", "models", "message"),
    [
        ("..", ["a", "b"], "run-id may contain only"),
        ("safe-run", ["..", "b"], "Model IDs contain unsupported"),
        ("unsafe/run", ["a", "b"], "run-id may contain only"),
    ],
)
@override_settings(OPENAI_API_KEY="test-only-key")
def test_evaluation_rejects_identifiers_that_could_escape_report_directories(
    tmp_path, run_id, models, message
):
    image_dir = tmp_path / "images"
    make_images(image_dir)

    with pytest.raises(CommandError, match=message):
        call_command(
            "evaluate_ai_models",
            **command_options(
                image_dir,
                tmp_path / "output",
                run_id=run_id,
                models=models,
            ),
        )


@pytest.mark.parametrize("image_count", [9, 16])
@override_settings(OPENAI_API_KEY="test-only-key")
def test_evaluation_requires_same_set_of_ten_to_fifteen_images(tmp_path, image_count):
    image_dir = tmp_path / "images"
    make_images(image_dir, image_count)

    with pytest.raises(CommandError, match="10 to 15"):
        call_command(
            "evaluate_ai_models",
            **command_options(image_dir, tmp_path / "output"),
        )


@override_settings(OPENAI_API_KEY="test-only-key")
def test_evaluation_stops_before_billable_calls_when_service_lacks_a_model(tmp_path):
    image_dir = tmp_path / "images"
    make_images(image_dir)

    with (
        patch.object(Command, "_build_client", return_value=Mock()),
        patch.object(Command, "_available_model_ids", return_value={"vision-a"}),
        patch.object(Command, "_evaluate_analysis") as evaluate,
        pytest.raises(CommandError, match="does not provide: vision-b"),
    ):
        call_command(
            "evaluate_ai_models",
            **command_options(image_dir, tmp_path / "output"),
        )

    evaluate.assert_not_called()


@override_settings(OPENAI_API_KEY="test-only-key")
def test_analysis_evaluation_records_every_model_image_pair_and_isolates_failures(tmp_path):
    image_dir = tmp_path / "images"
    output_dir = tmp_path / "output"
    make_images(image_dir)

    def evaluate(_command, _client, model, image_path):
        if model == "vision-b" and image_path.name == "image-09.png":
            raise RuntimeError("sk-private-value https://private-service.invalid")
        return {
            "latency_ms": 25,
            "prompt_version": "analysis-v1.0",
            "primary_subject": "一只猫",
            "subject_count": 1,
            "suitability": "suitable",
            "recommended_grid_size": 50,
            "recommended_color_limit": 24,
            "human_subject_correct": "pending",
            "human_region_correct": "pending",
            "human_chinese_clear": "pending",
        }

    with (
        patch.object(Command, "_build_client", return_value=Mock()),
        patch.object(
            Command,
            "_available_model_ids",
            return_value={"vision-a", "vision-b"},
        ),
        patch.object(Command, "_evaluate_analysis", autospec=True, side_effect=evaluate),
    ):
        call_command(
            "evaluate_ai_models",
            **command_options(image_dir, output_dir),
        )

    report = output_dir / "evaluation-01-analysis.csv"
    with report.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))

    assert len(rows) == 20
    assert sum(row["status"] == "success" for row in rows) == 19
    failed = next(row for row in rows if row["status"] == "failed")
    assert failed["error_type"] == "RuntimeError"
    assert all(row["human_review"] == "pending" for row in rows)
    assert all(row["billing_review"] == "pending_provider_invoice" for row in rows)
    report_text = report.read_text(encoding="utf-8")
    assert "sk-private-value" not in report_text
    assert "private-service.invalid" not in report_text


def test_advanced_evaluation_writes_a_separate_reviewable_output(tmp_path):
    image_path = tmp_path / "source.png"
    Image.new("RGB", (32, 32), (80, 120, 160)).save(image_path)
    edited = BytesIO()
    Image.new("RGB", (32, 32), (90, 130, 170)).save(edited, format="PNG")
    provider = Mock()
    provider.edit.return_value = SimpleNamespace(image_bytes=edited.getvalue(), latency_ms=40)
    output_dir = tmp_path / "output"

    with patch(
        "apps.operations.management.commands.evaluate_ai_models.OpenAIImageEditProvider",
        return_value=provider,
    ):
        row = Command()._evaluate_advanced(
            Mock(),
            "image-model",
            image_path,
            output_dir=output_dir,
            run_id="advanced-01",
            index=1,
            operation="style_transfer",
            instruction="转换为拼豆插画",
        )

    assert (output_dir / row["output_file"]).read_bytes() == edited.getvalue()
    assert row["latency_ms"] == 40
    assert row["automated_review_status"] in {"passed", "warning", "retry", "failed"}
    assert row["human_identity_preserved"] == "pending"
