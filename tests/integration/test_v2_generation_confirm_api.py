from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.creation.models import GenerationSettings, GenerationStatus
from apps.creation.services import create_generation_task
from apps.memberships.models import GenerationQuotaLedger
from apps.memberships.services import get_or_create_current_quota

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@pytest.fixture
def prepared_task(django_user_model):
    user = django_user_model.objects.create_user(username="api-owner", password="safe-password")
    task, _ = create_generation_task(user=user, idempotency_key="api-confirm-task")
    task.status = GenerationStatus.AWAITING_CONFIRMATION
    task.save(update_fields=("status", "updated_at"))
    GenerationSettings.objects.create(
        task=task,
        grid_size=29,
        grid_width=29,
        grid_height=29,
        color_limit=12,
        background_mode="keep",
    )
    return user, task


def test_confirm_api_requires_authenticated_user(client, prepared_task):
    _, task = prepared_task

    response = client.post(f"/api/v1/generation-tasks/{task.pk}/confirm/")

    assert response.status_code == 401
    assert response.json() == {"detail": "请先登录后再确认生成。"}


@patch("apps.creation.api.run_generation_task.delay")
def test_confirm_api_reserves_one_image_and_returns_status_url(mock_delay, client, prepared_task):
    user, task = prepared_task
    client.force_login(user)

    response = client.post(f"/api/v1/generation-tasks/{task.pk}/confirm/")

    assert response.status_code == 202
    assert response.json() == {
        "task_id": str(task.pk),
        "status": GenerationStatus.QUOTA_RESERVED,
        "status_url": f"/create/{task.pk}/status/",
        "progress_url": f"/create/{task.pk}/progress/",
        "idempotent": False,
    }
    task.refresh_from_db()
    assert task.status == GenerationStatus.QUOTA_RESERVED
    reservations = GenerationQuotaLedger.objects.filter(task_reference=task.pk, event="reserve")
    assert reservations.count() == 1
    mock_delay.assert_called_once_with(str(task.pk))


@patch("apps.creation.api.run_generation_task.delay")
def test_confirm_api_is_idempotent_after_reservation(mock_delay, client, prepared_task):
    user, task = prepared_task
    client.force_login(user)
    endpoint = f"/api/v1/generation-tasks/{task.pk}/confirm/"

    first = client.post(endpoint)
    second = client.post(endpoint)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["idempotent"] is True
    reservations = GenerationQuotaLedger.objects.filter(task_reference=task.pk, event="reserve")
    assert reservations.count() == 1
    mock_delay.assert_called_once_with(str(task.pk))


def test_confirm_api_rejects_unprepared_or_other_users_task(
    client, django_user_model, prepared_task
):
    user, task = prepared_task
    other = django_user_model.objects.create_user(username="api-other", password="safe-password")
    client.force_login(other)

    hidden = client.post(f"/api/v1/generation-tasks/{task.pk}/confirm/")

    assert hidden.status_code == 404

    client.force_login(user)
    task.settings.delete()
    unprepared = client.post(f"/api/v1/generation-tasks/{task.pk}/confirm/")

    assert unprepared.status_code == 409
    assert unprepared.json() == {"detail": "请先在页面完成图纸参数设置。"}


def test_confirm_api_reports_insufficient_quota(client, prepared_task):
    user, task = prepared_task
    client.force_login(user)
    quota = get_or_create_current_quota(user)
    quota.total_limit = 0
    quota.save(update_fields=("total_limit", "updated_at"))

    response = client.post(f"/api/v1/generation-tasks/{task.pk}/confirm/")

    assert response.status_code == 409
    assert response.json() == {"detail": "你本周期的生成张数已经用完。"}
    task.refresh_from_db()
    assert task.status == GenerationStatus.AWAITING_CONFIRMATION
