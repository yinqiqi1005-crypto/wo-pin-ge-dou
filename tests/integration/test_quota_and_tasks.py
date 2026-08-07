from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import close_old_connections
from django.test import override_settings
from PIL import Image

from apps.creation.analysis import execute_analysis_task
from apps.creation.models import GenerationSettings, GenerationStatus, GenerationTask
from apps.creation.services import create_generation_task
from apps.creation.state import InvalidTaskTransition, transition_task
from apps.creation.tasks import execute_generation_task
from apps.memberships.models import GenerationQuotaLedger, QuotaLedgerEvent
from apps.memberships.services import (
    InsufficientGenerationQuota,
    consume_generation,
    get_or_create_current_quota,
    release_generation,
    reserve_generation,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="quota-worker")


def task_with_image(user, *, key="task-one"):
    task, _ = create_generation_task(user=user, idempotency_key=key)
    image = Image.new("RGB", (60, 60), (210, 60, 60))
    output = BytesIO()
    image.save(output, format="PNG")
    task.input_image = SimpleUploadedFile("sample.png", output.getvalue(), content_type="image/png")
    task.save(update_fields=("input_image", "updated_at"))
    execute_analysis_task(str(task.pk))
    task.refresh_from_db()
    GenerationSettings.objects.create(
        task=task,
        grid_size=30,
        color_limit=12,
        background_mode="keep",
    )
    return task


def test_quota_reservation_and_consumption_are_idempotent(user):
    task = task_with_image(user)

    first_quota = reserve_generation(task)
    second_quota = reserve_generation(task)
    task.refresh_from_db()

    assert first_quota.pk == second_quota.pk
    assert task.status == GenerationStatus.QUOTA_RESERVED
    assert task.quota_period.reserved_count == 1
    assert GenerationQuotaLedger.objects.filter(event=QuotaLedgerEvent.RESERVE).count() == 1

    consume_generation(task)
    consume_generation(task)
    task.quota_period.refresh_from_db()

    assert task.quota_period.reserved_count == 0
    assert task.quota_period.used_count == 1
    assert GenerationQuotaLedger.objects.filter(event=QuotaLedgerEvent.CONSUME).count() == 1


def test_quota_cannot_be_reserved_past_limit(user):
    quota = get_or_create_current_quota(user)
    quota.total_limit = 1
    quota.save(update_fields=("total_limit", "updated_at"))
    first = task_with_image(user, key="first")
    second = task_with_image(user, key="second")

    reserve_generation(first)

    with pytest.raises(InsufficientGenerationQuota, match="已经用完"):
        reserve_generation(second)
    quota.refresh_from_db()
    assert quota.reserved_count == 1
    assert quota.used_count == 0


def test_release_returns_reserved_image_and_is_idempotent(user):
    task = task_with_image(user)
    reserve_generation(task)

    release_generation(task)
    release_generation(task)
    task.quota_period.refresh_from_db()

    assert task.quota_period.reserved_count == 0
    assert task.quota_period.used_count == 0
    assert GenerationQuotaLedger.objects.filter(event=QuotaLedgerEvent.RELEASE).count() == 1


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-task-test-media")
def test_successful_background_task_consumes_one_image(user):
    task = task_with_image(user)
    reserve_generation(task)

    completed = execute_generation_task(str(task.pk))
    completed.quota_period.refresh_from_db()

    assert completed.status == GenerationStatus.SUCCEEDED
    assert completed.result_version_id is not None
    assert completed.quota_period.used_count == 1
    assert completed.quota_period.reserved_count == 0
    assert completed.retry_count == 0


def test_failed_background_task_retries_once_and_releases_quota(user):
    task = task_with_image(user)
    reserve_generation(task)

    with patch(
        "apps.creation.tasks.generate_basic_pattern", side_effect=RuntimeError("boom")
    ) as call:
        completed = execute_generation_task(str(task.pk))
    completed.quota_period.refresh_from_db()

    assert call.call_count == 2
    assert completed.status == GenerationStatus.FAILED
    assert completed.retry_count == 2
    assert completed.quota_period.used_count == 0
    assert completed.quota_period.reserved_count == 0
    assert completed.progress_message == "本次生成未完成，预留张数已经释放。"


def test_illegal_task_state_transition_is_rejected(user):
    task = task_with_image(user)

    with pytest.raises(InvalidTaskTransition, match="Cannot transition"):
        transition_task(task, GenerationStatus.SAVED)


def test_status_endpoint_reports_durable_task_state(client, user):
    client.force_login(user)
    task = task_with_image(user)
    reserve_generation(task)
    task.refresh_from_db()

    response = client.get(f"/create/{task.pk}/status/")

    assert response.status_code == 200
    assert response.json()["status"] == GenerationStatus.QUOTA_RESERVED
    assert response.json()["result_url"] is None


def test_queued_task_can_be_cancelled_and_quota_is_released(client, user):
    client.force_login(user)
    task = task_with_image(user)
    reserve_generation(task)
    transition_task(task, GenerationStatus.QUEUED, stage="queued", message="任务已进入队列。")

    response = client.post(f"/create/{task.pk}/cancel/")
    task.refresh_from_db()
    task.quota_period.refresh_from_db()

    assert response.status_code == 302
    assert task.status == GenerationStatus.CANCELLED
    assert task.quota_period.reserved_count == 0
    assert task.quota_period.used_count == 0


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_tasks_cannot_reserve_one_remaining_image(django_user_model):
    call_command("seed_demo_config", verbosity=0)
    concurrent_user = django_user_model.objects.create_user(username="concurrent-user")
    quota = get_or_create_current_quota(concurrent_user)
    quota.total_limit = 1
    quota.save(update_fields=("total_limit", "updated_at"))
    first = task_with_image(concurrent_user, key="concurrent-first")
    second = task_with_image(concurrent_user, key="concurrent-second")
    barrier = Barrier(2)

    def attempt(task_id):
        close_old_connections()
        task = GenerationTask.objects.get(pk=task_id)
        barrier.wait()
        try:
            reserve_generation(task)
        except InsufficientGenerationQuota:
            return "insufficient"
        finally:
            close_old_connections()
        return "reserved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (first.pk, second.pk)))

    quota.refresh_from_db()
    assert sorted(results) == ["insufficient", "reserved"]
    assert quota.reserved_count == 1
    assert quota.used_count == 0
