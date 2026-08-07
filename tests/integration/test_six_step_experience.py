from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image

from apps.creation.models import GenerationStatus, GenerationTask, ModelCallLog
from apps.memberships.services import get_or_create_current_quota

pytestmark = pytest.mark.django_db


def uploaded_png(name="experience.png"):
    image = Image.new("RGB", (100, 100), (190, 70, 65))
    output = BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@pytest.fixture
def creator(client, django_user_model):
    user = django_user_model.objects.create_user(username="experience-user")
    client.force_login(user)
    return client, user


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m6-media")
def test_upload_supports_accessible_click_drop_and_recent_task_recovery(creator):
    client, user = creator
    page = client.get("/create/").content.decode()

    assert "data-drop-upload" in page
    assert "拖拽图片到这里，或点击选择" in page
    assert 'aria-live="polite"' in page

    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    recovery_page = client.get("/create/").content.decode()
    assert "最近的创作任务" in recovery_page
    assert f"/create/{task.pk}/analysis/" in recovery_page


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m6-media")
def test_uncertain_subject_can_be_reselected_without_another_model_call(creator):
    client, user = creator
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    before = ModelCallLog.objects.filter(task=task).count()
    analysis_page = client.get(f"/create/{task.pk}/analysis/").content.decode()

    assert "重新选择主体区域" in analysis_page
    assert analysis_page.count('class="notice"') <= 3

    response = client.post(
        f"/create/{task.pk}/analysis/",
        {"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6},
    )
    task.refresh_from_db()

    assert response.status_code == 302
    assert response.url == f"/create/{task.pk}/settings/"
    assert task.analysis.subject_region == {"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}
    assert task.settings.selected_subject == task.analysis.subject_region
    assert ModelCallLog.objects.filter(task=task).count() == before


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m6-media")
def test_quota_error_keeps_generation_settings_and_explains_one_image_cost(creator):
    client, user = creator
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    quota = get_or_create_current_quota(user)
    quota.total_limit = 0
    quota.save(update_fields=("total_limit", "updated_at"))

    response = client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 70, "color_limit": 36, "background_mode": "keep"},
    )

    assert response.status_code == 200
    assert response.context["form"].data["grid_size"] == "70"
    content = response.content.decode()
    assert "已经用完" in content
    assert "本次成功后使用 1 张" in content


def test_progress_shows_five_named_stages_and_free_retry_message(creator):
    client, user = creator
    task = GenerationTask.objects.create(
        user=user,
        idempotency_key="queued-experience",
        status=GenerationStatus.QUEUED,
        retry_count=1,
    )

    content = client.get(f"/create/{task.pk}/progress/").content.decode()

    for stage in ("准备图片", "优化颜色", "生成网格", "校验图纸", "保存结果"):
        assert stage in content
    assert "免费自动优化，不会重复计算张数" in content


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m6-media")
def test_result_has_three_sections_guidance_and_save_error_is_near_form(creator):
    client, user = creator
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    task.refresh_from_db()

    result_page = client.get(f"/create/{task.pk}/result/").content.decode()
    assert "效果图" in result_page
    assert "网格图" in result_page
    assert "材料与建议" in result_page
    assert "难度：入门" in result_page
    assert "放大查看带编号网格图" in result_page

    invalid_save = client.post(f"/create/{task.pk}/save/", {"title": "", "note": ""})
    assert invalid_save.status_code == 200
    assert "这个字段是必填项" in invalid_save.content.decode()
