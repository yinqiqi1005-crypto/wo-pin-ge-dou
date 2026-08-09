from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.core.middleware import LanguagePreferenceMiddleware
from apps.creation.models import GenerationSettings, GenerationStatus
from apps.creation.services import create_generation_task

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)
    cache.clear()


@pytest.mark.parametrize(
    ("language", "expected"),
    (("ja", "会員プラン"), ("ko", "멤버십 플랜")),
)
def test_japanese_and_korean_cover_membership_function_page(
    client, django_user_model, language, expected
):
    user = django_user_model.objects.create_user(username=f"member-{language}")
    user.profile.preferred_language = language
    user.profile.save(update_fields=("preferred_language", "updated_at"))
    client.force_login(user)

    response = client.get(reverse("memberships:plans"))

    assert response.status_code == 200
    assert expected in response.content.decode()


def test_admin_response_is_not_translated_for_a_non_chinese_user(django_user_model):
    user = django_user_model.objects.create_user(username="admin-language")
    user.profile.preferred_language = "ja"
    user.profile.save(update_fields=("preferred_language", "updated_at"))
    request = RequestFactory().get("/admin/")
    request.user = user
    request.session = {}

    response = LanguagePreferenceMiddleware(lambda _: HttpResponse("AI 创作"))(request)

    assert response.content.decode() == "AI 创作"


@patch("apps.creation.api.run_generation_task.delay")
def test_confirm_api_limits_obvious_high_frequency_calls(mock_delay, client, django_user_model):
    user = django_user_model.objects.create_user(username="api-rate-limit")
    task, _ = create_generation_task(user=user, idempotency_key="rate-limit-task")
    task.status = GenerationStatus.AWAITING_CONFIRMATION
    task.save(update_fields=("status", "updated_at"))
    GenerationSettings.objects.create(
        task=task,
        grid_size=29,
        color_limit=12,
        background_mode="keep",
    )
    client.force_login(user)
    endpoint = f"/api/v1/generation-tasks/{task.pk}/confirm/"

    responses = [client.post(endpoint) for _ in range(20)]
    limited = client.post(endpoint)

    assert all(response.status_code == 202 for response in responses)
    assert limited.status_code == 429
    assert limited.json() == {"detail": "请求过于频繁，请稍后再试。"}
    mock_delay.assert_called_once_with(str(task.pk))
