from io import BytesIO
from time import monotonic
from unittest.mock import patch

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image

from apps.creation.analysis import execute_analysis_task
from apps.creation.models import GenerationSettings, GenerationStatus, GenerationTask
from apps.creation.services import create_generation_task
from apps.creation.tasks import execute_generation_task
from apps.memberships.models import MembershipSubscription
from apps.memberships.services import reserve_generation

pytestmark = pytest.mark.django_db


def png_bytes():
    output = BytesIO()
    Image.new("RGB", (80, 80), (180, 90, 70)).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m9-media")
def test_oversized_but_decodable_image_is_rejected_without_task(client, django_user_model):
    user = django_user_model.objects.create_user(username="oversized-user")
    client.force_login(user)
    oversized = SimpleUploadedFile(
        "oversized.png",
        png_bytes() + b"0" * (10 * 1024 * 1024),
        content_type="image/png",
    )

    response = client.post("/create/", {"image": oversized})

    assert response.status_code == 200
    assert "图片不能超过 10 MB" in response.content.decode()
    assert GenerationTask.objects.filter(user=user).exists() is False


class SensitiveFailureProvider:
    provider_name = "openai"
    model_name = "private-model"

    def analyze(self, image_bytes, *, media_type):
        raise ConnectionError("sk-secret-value https://private-model.internal/v1")


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m9-media")
def test_provider_failure_logs_do_not_expose_keys_or_private_addresses(caplog, django_user_model):
    user = django_user_model.objects.create_user(username="safe-log-user")
    task, _ = create_generation_task(user=user, idempotency_key="safe-log")
    task.configuration_snapshot["model_routes"]["analysis"] = {
        "provider": "openai",
        "model": "private-model",
        "max_attempts": 2,
    }
    task.input_image = SimpleUploadedFile("safe.png", png_bytes(), content_type="image/png")
    task.save(update_fields=("configuration_snapshot", "input_image", "updated_at"))

    with patch(
        "apps.creation.analysis.get_analysis_provider",
        return_value=SensitiveFailureProvider(),
    ):
        execute_analysis_task(str(task.pk))

    assert "sk-secret-value" not in caplog.text
    assert "private-model.internal" not in caplog.text
    assert set(task.model_calls.values_list("error_type", flat=True)) == {
        "ConnectionError",
        "",
    }


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-demo-command-media")
def test_prepare_demo_creates_three_tier_accounts_and_stable_images(django_user_model):
    call_command("prepare_demo", password="Portfolio-Demo-2026", verbosity=0)

    assert (
        django_user_model.objects.filter(
            username__in=("demo_registered", "demo_plus", "demo_pro")
        ).count()
        == 3
    )
    assert MembershipSubscription.objects.filter(user__username="demo_plus").exists()
    assert MembershipSubscription.objects.filter(user__username="demo_pro").exists()
    for filename in ("demo-person.png", "demo-pet.png", "demo-object.png"):
        assert default_storage.exists(f"demo-assets/{filename}")


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m9-media")
def test_persisted_reserved_task_recovers_after_worker_boundary_within_local_baseline(
    django_user_model,
):
    user = django_user_model.objects.create_user(username="restart-recovery")
    task, _ = create_generation_task(user=user, idempotency_key="restart-recovery")
    task.input_image = SimpleUploadedFile("restart.png", png_bytes(), content_type="image/png")
    task.save(update_fields=("input_image", "updated_at"))
    execute_analysis_task(str(task.pk))
    GenerationSettings.objects.create(
        task=task, grid_size=30, color_limit=12, background_mode="keep"
    )
    task.refresh_from_db()
    reserve_generation(task)

    del task
    started = monotonic()
    recovered = execute_generation_task(
        str(GenerationTask.objects.get(idempotency_key="restart-recovery").pk)
    )

    assert recovered.status == GenerationStatus.SUCCEEDED
    assert recovered.result_version.validation_result["technical"] == "passed"
    assert monotonic() - started < 10
