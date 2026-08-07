from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image

from apps.creation.analysis import execute_analysis_task
from apps.creation.models import GenerationStatus, ModelCallLog
from apps.creation.services import create_generation_task
from apps.memberships.models import GenerationQuotaLedger

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@pytest.fixture
def analysis_task(django_user_model):
    user = django_user_model.objects.create_user(username="analysis-user")
    task, _ = create_generation_task(user=user, idempotency_key="analysis-task")
    output = BytesIO()
    Image.new("RGB", (120, 100), (180, 70, 60)).save(output, format="PNG")
    task.input_image = SimpleUploadedFile(
        "subject.png", output.getvalue(), content_type="image/png"
    )
    task.save(update_fields=("input_image", "updated_at"))
    return task


class BrokenProvider:
    provider_name = "openai"
    model_name = "broken-model"

    def analyze(self, image_bytes, *, media_type):
        raise TimeoutError("provider timeout")


@override_settings(AI_ANALYSIS_PROVIDER="openai", AI_ANALYSIS_MAX_ATTEMPTS=2)
def test_provider_failure_retries_then_falls_back_without_using_quota(analysis_task):
    analysis_task.configuration_snapshot["model_routes"]["analysis"] = {
        "provider": "openai",
        "model": "broken-model",
        "max_attempts": 2,
    }
    analysis_task.save(update_fields=("configuration_snapshot", "updated_at"))
    with patch("apps.creation.analysis.get_analysis_provider", return_value=BrokenProvider()):
        completed = execute_analysis_task(str(analysis_task.pk))

    completed.refresh_from_db()
    logs = list(ModelCallLog.objects.filter(task=completed))
    assert completed.status == GenerationStatus.AWAITING_CONFIRMATION
    assert completed.analysis.model_name == "rule-analysis-v1"
    assert [(log.provider, log.success) for log in logs] == [
        ("openai", False),
        ("openai", False),
        ("rules", True),
    ]
    assert GenerationQuotaLedger.objects.count() == 0
    assert completed.quota_period_id is None


def test_uncertain_analysis_saves_a_reselectable_subject_mask(analysis_task):
    completed = execute_analysis_task(str(analysis_task.pk))

    assert completed.analysis.requires_subject_confirmation is True
    assert completed.analysis.subject_mask.name.endswith("-subject.png")


def test_analysis_is_idempotent_after_success(analysis_task):
    execute_analysis_task(str(analysis_task.pk))

    with patch("apps.creation.analysis.get_analysis_provider") as provider_factory:
        execute_analysis_task(str(analysis_task.pk))

    provider_factory.assert_not_called()
    assert ModelCallLog.objects.filter(task=analysis_task).count() == 1
    assert str(ModelCallLog.objects.get(task=analysis_task).internal_cost) == "0.006000"
