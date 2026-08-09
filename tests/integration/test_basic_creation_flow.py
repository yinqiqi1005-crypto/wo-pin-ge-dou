from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError
from django.test import override_settings
from PIL import Image

from apps.creation.models import GenerationStatus, GenerationTask
from apps.patterns.models import Pattern

pytestmark = pytest.mark.django_db


def uploaded_png(name="sample.png"):
    image = Image.new("RGB", (80, 80), (220, 70, 70))
    output = BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@pytest.fixture
def signed_in_client(client, django_user_model):
    user = django_user_model.objects.create_user(username="creator", password="safe-password")
    client.force_login(user)
    return client, user


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-test-media")
def test_upload_creates_task_and_structured_analysis(signed_in_client):
    client, user = signed_in_client

    response = client.post("/create/", {"image": uploaded_png()})

    task = GenerationTask.objects.get(user=user)
    assert response.status_code == 302
    assert response.url == f"/create/{task.pk}/analysis/"
    assert task.status == GenerationStatus.AWAITING_CONFIRMATION
    assert task.analysis.recommendations["grid_size"] == 50


def test_upload_rejects_non_image_file(signed_in_client):
    client, user = signed_in_client
    invalid = SimpleUploadedFile("notes.txt", b"not-an-image", content_type="text/plain")

    response = client.post("/create/", {"image": invalid})

    assert response.status_code == 200
    assert "请上传一张有效的 JPG 或 PNG 图片，文件不能损坏" in response.content.decode()
    assert GenerationTask.objects.filter(user=user).exists() is False


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-test-media")
def test_registered_user_can_generate_save_and_view_pattern(signed_in_client):
    client, user = signed_in_client
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)

    response = client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    task.refresh_from_db()

    assert response.status_code == 302
    assert response.url == f"/create/{task.pk}/progress/"
    assert task.status == GenerationStatus.SUCCEEDED
    version = task.result_version
    assert version.grid_data["width"] == 30
    assert sum(version.material_counts.values()) == 900
    assert version.total_beads == 900
    assert version.effect_preview.name.endswith(".png")
    assert version.grid_preview.name.endswith(".png")
    assert version.pattern.is_saved is False

    response = client.post(
        f"/create/{task.pk}/save/",
        {"title": "红色方块", "note": "第一张测试图纸"},
    )
    task.refresh_from_db()
    pattern = Pattern.objects.get(owner=user)

    assert response.status_code == 302
    assert response.url == f"/patterns/{pattern.pk}/"
    assert pattern.title == "红色方块"
    assert pattern.is_saved is True
    assert task.status == GenerationStatus.SAVED

    library_response = client.get("/patterns/")
    detail_response = client.get(f"/patterns/{pattern.pk}/")
    assert "红色方块" in library_response.content.decode()
    assert "第一张测试图纸" in detail_response.content.decode()


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-test-media")
def test_result_modal_save_returns_json_without_page_redirect(signed_in_client):
    client, user = signed_in_client
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )

    result = client.get(f"/create/{task.pk}/result/")
    assert "data-save-pattern-modal" in result.content.decode()
    assert 'aria-modal="true"' in result.content.decode()
    category_id = user.pattern_categories.first().pk
    saved = client.post(
        f"/create/{task.pk}/save/",
        {"title": "弹窗保存", "category_id": category_id, "note": "无需刷新"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert saved.status_code == 200
    assert saved.json()["saved"] is True
    pattern = Pattern.objects.get(owner=user)
    assert pattern.category_id == category_id


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-test-media")
def test_result_modal_returns_specific_save_error_without_losing_form_data(signed_in_client):
    client, user = signed_in_client
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    category_id = user.pattern_categories.first().pk

    with patch("apps.patterns.models.Pattern.save", side_effect=DatabaseError("temporary")):
        response = client.post(
            f"/create/{task.pk}/save/",
            {"title": "保留输入", "category_id": category_id, "note": "仍在弹窗内"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    assert response.status_code == 500
    assert response.json()["errors"]["__all__"][0]["message"] == "作品暂时无法保存，请稍后重试。"
    task.refresh_from_db()
    assert task.result_version.pattern.is_saved is False


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-test-media")
def test_user_cannot_access_another_users_task_or_pattern(client, django_user_model):
    owner = django_user_model.objects.create_user(username="owner", password="password")
    stranger = django_user_model.objects.create_user(username="stranger", password="password")
    client.force_login(owner)
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=owner)
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    client.post(f"/create/{task.pk}/save/", {"title": "Private", "note": ""})
    pattern = Pattern.objects.get(owner=owner)

    client.force_login(stranger)

    assert client.get(f"/create/{task.pk}/analysis/").status_code == 404
    assert client.get(f"/create/{task.pk}/result/").status_code == 404
    assert client.get(f"/patterns/{pattern.pk}/").status_code == 404


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-test-media")
def test_remove_background_creates_blank_cells(signed_in_client):
    client, user = signed_in_client
    image = Image.new("RGB", (80, 80), (255, 255, 255))
    for y in range(20, 60):
        for x in range(20, 60):
            image.putpixel((x, y), (210, 55, 60))
    output = BytesIO()
    image.save(output, format="PNG")
    upload = SimpleUploadedFile("subject.png", output.getvalue(), content_type="image/png")
    client.post("/create/", {"image": upload})
    task = GenerationTask.objects.get(user=user)

    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "remove"},
    )
    task.refresh_from_db()
    cells = task.result_version.grid_data["cells"]

    assert any(cell is None for row in cells for cell in row)
    assert any(cell is not None for row in cells for cell in row)
