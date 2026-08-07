from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from PIL import Image

from apps.creation.models import GenerationMode, GenerationStatus, GenerationTask
from apps.memberships.models import MembershipPlan, MembershipSubscription
from apps.memberships.services import get_or_create_current_quota
from apps.patterns.models import Pattern

pytestmark = pytest.mark.django_db


def uploaded_png():
    image = Image.new("RGB", (120, 120), (220, 210, 190))
    for y in range(28, 92):
        for x in range(28, 92):
            image.putpixel((x, y), (80, 100, 170))
    output = BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile("advanced.png", output.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


def subscribe(user, level):
    plan = MembershipPlan.objects.get(level=level)
    MembershipSubscription.objects.create(
        user=user,
        plan=plan,
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=30),
    )
    return plan


def create_saved_pattern(client, user):
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.filter(user=user).latest("created_at")
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    task.refresh_from_db()
    client.post(f"/create/{task.pk}/save/", {"title": "高级创作底图", "note": ""})
    return Pattern.objects.get(owner=user), task


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m7-media")
def test_registered_member_cannot_use_advanced_capability(client, django_user_model):
    user = django_user_model.objects.create_user(username="registered-only")
    client.force_login(user)
    pattern, _ = create_saved_pattern(client, user)
    version = pattern.latest_version

    page = client.get(f"/patterns/{pattern.pk}/versions/{version.version_number}/advanced/")
    before = GenerationTask.objects.filter(user=user, mode=GenerationMode.ADVANCED).count()
    response = client.post(
        f"/patterns/{pattern.pk}/versions/{version.version_number}/advanced/",
        {
            "operation": "style_transfer",
            "instruction": "温暖插画",
            "preserve_content": "主体身份",
            "editable_content": "背景,色彩",
        },
    )

    assert "当前会员没有高级创作权限" in page.content.decode()
    assert response.status_code == 200
    assert GenerationTask.objects.filter(user=user, mode=GenerationMode.ADVANCED).count() == before


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m7-media")
def test_plus_content_creation_adds_child_version_and_consumes_one(client, django_user_model):
    user = django_user_model.objects.create_user(username="plus-creator")
    subscribe(user, "plus")
    client.force_login(user)
    pattern, basic_task = create_saved_pattern(client, user)
    source = pattern.latest_version
    quota = get_or_create_current_quota(user)
    used_before = quota.used_count

    response = client.post(
        f"/patterns/{pattern.pk}/versions/{source.version_number}/advanced/",
        {
            "operation": "style_transfer",
            "instruction": "提高色彩层次",
            "preserve_content": "主体身份,姿态,关键特征",
            "editable_content": "背景,色彩",
        },
    )
    task = GenerationTask.objects.filter(user=user, mode=GenerationMode.ADVANCED).get()
    quota.refresh_from_db()

    assert response.status_code == 302
    assert task.status == GenerationStatus.SUCCEEDED
    assert pattern.versions.count() == 2
    assert task.result_version.parent_version_id == source.pk
    assert task.result_version.validation_result["technical"] == "passed"
    assert task.result_version.validation_result["visual_review"]["status"] in {
        "passed",
        "warning",
    }
    assert quota.used_count == used_before + 1
    assert basic_task.result_version_id == source.pk


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m7-media")
def test_parameter_adjustment_reuses_base_and_does_not_use_quota(client, django_user_model):
    user = django_user_model.objects.create_user(username="free-adjuster")
    subscribe(user, "plus")
    client.force_login(user)
    pattern, _ = create_saved_pattern(client, user)
    source = pattern.latest_version
    quota = get_or_create_current_quota(user)
    used_before = quota.used_count

    response = client.post(
        f"/patterns/{pattern.pk}/versions/{source.version_number}/adjust/",
        {"grid_size": 50, "color_limit": 24, "background_mode": "simplify"},
    )
    quota.refresh_from_db()
    latest = pattern.versions.order_by("-version_number").first()

    assert response.status_code == 302
    assert latest.parent_version_id == source.pk
    assert latest.settings_snapshot["change_type"] == "parameter"
    assert latest.grid_data["width"] == 50
    assert quota.used_count == used_before


class BrokenAdvancedProvider:
    provider_name = "openai"
    model_name = "broken-image-model"

    def edit(self, *args, **kwargs):
        raise TimeoutError("image provider timeout")


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m7-media")
def test_advanced_failure_retries_once_releases_quota_and_preserves_old_version(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="failed-advanced")
    subscribe(user, "pro")
    client.force_login(user)
    pattern, _ = create_saved_pattern(client, user)
    source = pattern.latest_version
    quota = get_or_create_current_quota(user)
    used_before = quota.used_count

    with patch(
        "apps.creation.advanced.get_advanced_provider",
        return_value=BrokenAdvancedProvider(),
    ):
        client.post(
            f"/patterns/{pattern.pk}/versions/{source.version_number}/advanced/",
            {
                "operation": "background_creation",
                "instruction": "增加渐变背景",
                "preserve_content": "主体身份",
                "editable_content": "背景",
            },
        )
    task = GenerationTask.objects.filter(user=user, mode=GenerationMode.ADVANCED).get()
    quota.refresh_from_db()

    assert task.status == GenerationStatus.FAILED
    assert task.model_calls.filter(capability="image_edit").count() == 2
    assert pattern.versions.count() == 1
    assert pattern.latest_version.pk == source.pk
    assert quota.used_count == used_before
    assert quota.reserved_count == 0
