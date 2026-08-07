from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image

from apps.accounts.models import UserProfile
from apps.creation.models import GenerationTask
from apps.patterns.models import Pattern

pytestmark = pytest.mark.django_db


def upload_image(name):
    output = BytesIO()
    Image.new("RGB", (90, 90), (190, 80, 65)).save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-guest-media")
def test_guest_can_generate_once_then_register_without_losing_result(client, django_user_model):
    upload_page = client.get("/create/")
    guest_profile = UserProfile.objects.get(is_guest=True)
    assert "免费游客" in upload_page.content.decode()

    client.post("/create/", {"image": upload_image("guest-first.png")})
    first = GenerationTask.objects.get(user=guest_profile.user)
    response = client.post(
        f"/create/{first.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    first.refresh_from_db()
    first.quota_period.refresh_from_db()

    assert response.status_code == 302
    assert first.quota_period.plan.level == "visitor"
    assert first.quota_period.total_limit == 1
    assert first.quota_period.used_count == 1

    save_gate = client.get(f"/create/{first.pk}/save/")
    assert save_gate.status_code == 302
    assert save_gate.url == f"/accounts/register/?next=/create/{first.pk}/save/"

    register = client.post(
        "/accounts/register/",
        {
            "username": "guest-became-member",
            "password1": "Safe-guest-password-2026",
            "password2": "Safe-guest-password-2026",
            "next": f"/create/{first.pk}/save/",
        },
    )
    user = django_user_model.objects.get(username="guest-became-member")
    first.refresh_from_db()

    assert register.status_code == 302
    assert register.url == f"/create/{first.pk}/save/"
    assert first.user == user
    assert first.result_version.pattern.owner == user

    saved = client.post(
        f"/create/{first.pk}/save/",
        {"title": "游客转正作品", "note": "结果没有丢失"},
    )
    assert saved.status_code == 302
    assert Pattern.objects.get(owner=user).title == "游客转正作品"


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-guest-media")
def test_guest_second_generation_keeps_settings_and_reports_no_remaining_images(client):
    client.get("/create/")
    client.post("/create/", {"image": upload_image("guest-one.png")})
    first = GenerationTask.objects.latest("created_at")
    client.post(
        f"/create/{first.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    client.post("/create/", {"image": upload_image("guest-two.png")})
    second = GenerationTask.objects.latest("created_at")

    response = client.post(
        f"/create/{second.pk}/settings/",
        {"grid_size": 50, "color_limit": 24, "background_mode": "keep"},
    )

    assert response.status_code == 200
    assert "已经用完" in response.content.decode()
    assert response.context["form"].data["grid_size"] == "50"
