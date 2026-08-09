from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError
from django.test import override_settings
from PIL import Image

from apps.creation.models import GenerationStatus, GenerationTask, ModelCallLog
from apps.memberships.models import FeatureCode, MembershipPlan
from apps.memberships.services import get_or_create_current_quota
from apps.patterns.models import Pattern

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
    assert "data-upload-preview" in page
    assert "正在上传……" in page

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
    assert "适配结果：可以尝试" in analysis_page
    assert 'class="subject-region"' in analysis_page
    assert "重新上传图片" in analysis_page
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
@pytest.mark.parametrize(
    ("suitability", "label"),
    [
        ("suitable", "适合生成"),
        ("try", "可以尝试"),
        ("not_suitable", "不太适合"),
        ("unprocessable", "无法处理"),
    ],
)
def test_analysis_renders_all_four_suitability_states_in_plain_language(
    creator, suitability, label
):
    client, user = creator
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    task.analysis.suitability_level = suitability
    task.analysis.save(update_fields=("suitability_level", "updated_at"))

    content = client.get(f"/create/{task.pk}/analysis/").content.decode()

    assert f"适配结果：{label}" in content


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
    assert content.count("你本周期的生成张数已经用完。") == 1
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
    assert "你在生成前的选择" in result_page
    assert "烫豆方式：标准双面半烫（保留豆孔）" in result_page
    assert "效果示意：AI 生成的说明图片" not in result_page
    assert "查看官方标准熔合示例" in result_page
    for panel_id in ("effect-panel", "grid-panel", "materials-panel"):
        assert f'id="{panel_id}" data-tab-panel' in result_page
        assert f'id="{panel_id}" data-tab-panel hidden' not in result_page

    invalid_save = client.post(f"/create/{task.pk}/save/", {"title": "", "note": ""})
    assert invalid_save.status_code == 200
    assert "这个字段是必填项" in invalid_save.content.decode()


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m6-media")
def test_basic_generation_permission_is_enforced_from_task_snapshot(creator):
    client, user = creator
    plan = MembershipPlan.objects.get(level="registered")
    plan.features.remove(plan.features.get(code=FeatureCode.BASIC_GENERATION))
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)

    response = client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    task.refresh_from_db()

    assert response.status_code == 200
    assert "当前会员配置未开放基础生成功能" in response.content.decode()
    assert task.status == GenerationStatus.AWAITING_CONFIRMATION
    assert task.quota_period_id is None


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m6-media")
def test_save_database_failure_preserves_generated_result_for_retry(creator):
    client, user = creator
    client.post("/create/", {"image": uploaded_png()})
    task = GenerationTask.objects.get(user=user)
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": 30, "color_limit": 12, "background_mode": "keep"},
    )
    task.refresh_from_db()

    with patch.object(Pattern, "save", side_effect=DatabaseError("database unavailable")):
        response = client.post(f"/create/{task.pk}/save/", {"title": "稍后保存", "note": ""})
    task.refresh_from_db()

    assert response.status_code == 200
    content = response.content.decode()
    assert "作品暂时无法保存，请稍后重试" in content
    assert content.count("作品暂时无法保存，请稍后重试。") == 1
    assert task.status == GenerationStatus.SUCCEEDED
    assert task.failure_code == "save_failed"
    assert task.result_version.pattern.is_saved is False
