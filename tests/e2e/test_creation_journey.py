import os
import re
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import DatabaseError
from django.test import override_settings
from PIL import Image

from apps.creation.models import GenerationStatus
from apps.creation.services import generate_basic_pattern as real_generate_basic_pattern
from apps.memberships.models import GenerationQuotaLedger, QuotaLedgerEvent
from apps.memberships.services import get_or_create_current_quota
from services.demo_assets import build_demo_images

pytestmark = pytest.mark.django_db(transaction=True)


def activate(page, locator, interaction):
    if interaction == "keyboard":
        locator.focus()
        assert locator.evaluate("element => document.activeElement === element")
        assert locator.evaluate("element => getComputedStyle(element).outlineStyle") != "none"
        page.keyboard.press("Enter")
    else:
        locator.click()


def signed_in_page(browser, live_server, django_user_model, username, *, viewport=None):
    call_command("seed_demo_config", verbosity=0)
    password = "E2E-safe-password"
    user = django_user_model.objects.create_user(username=username, password=password)
    page = browser.new_page(viewport=viewport or {"width": 1280, "height": 900})
    page.goto(f"{live_server.url}/accounts/login/")
    page.get_by_label("用户名").fill(username)
    page.get_by_label("密码").fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(re.compile(r"/create/$"))
    return page, user


def upload_for_analysis(page, image_bytes, *, filename="e2e-person.png"):
    page.locator("input[type=file]").set_input_files(
        {"name": filename, "mimeType": "image/png", "buffer": image_bytes}
    )
    page.get_by_role("button", name="上传并分析").click()
    page.wait_for_url(re.compile(r"/analysis/$"))
    page.get_by_role("heading", name="智能分析完成").wait_for()


def continue_to_settings(page):
    confirm = page.get_by_role("link", name="确认生成设置")
    if confirm.count():
        confirm.click()
    else:
        page.get_by_role("link", name=re.compile("仍然继续")).click()
    page.wait_for_url(re.compile(r"/settings/$"))


def choose_basic_settings(page, *, size="30", colors="12", background="keep"):
    page.get_by_label("图纸尺寸").select_option(size)
    page.get_by_label("颜色数量").select_option(colors)
    page.get_by_label("背景处理").select_option(background)


def main_journey_page(browser, viewport, interaction):
    destination_value = os.getenv("E2E_RECORD_VIDEO_PATH", "")
    should_record = (
        bool(destination_value) and viewport["width"] == 1280 and interaction == "pointer"
    )
    if not should_record:
        return browser.new_page(viewport=viewport), None, None
    destination = Path(destination_value)
    if destination.exists():
        raise AssertionError(f"Demo recording already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        viewport=viewport,
        record_video_dir=str(destination.parent),
        record_video_size=viewport,
    )
    return context.new_page(), context, destination


def close_main_journey_page(page, recording_context, recording_destination):
    if recording_context is None:
        page.close()
        return
    video = page.video
    recording_context.close()
    generated_path = Path(video.path())
    generated_path.rename(recording_destination)
    assert recording_destination.stat().st_size > 0


@pytest.mark.parametrize(
    ("viewport", "interaction"),
    [
        ({"width": 1280, "height": 900}, "pointer"),
        ({"width": 390, "height": 844}, "pointer"),
        ({"width": 1280, "height": 900}, "keyboard"),
    ],
    ids=("desktop", "mobile", "keyboard"),
)
@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-media")
def test_real_browser_completes_six_step_creation_and_save(
    browser,
    live_server,
    django_user_model,
    viewport,
    interaction,
):
    call_command("seed_demo_config", verbosity=0)
    username = f"e2e-{viewport['width']}-{interaction}"
    password = "E2E-safe-password"
    django_user_model.objects.create_user(username=username, password=password)
    page, recording_context, recording_destination = main_journey_page(
        browser,
        viewport,
        interaction,
    )

    page.goto(f"{live_server.url}/accounts/login/")
    if interaction == "keyboard":
        page.keyboard.press("Tab")
        assert page.locator(":focus").get_attribute("class") == "skip-link"
        page.keyboard.press("Enter")
        assert page.locator(":focus").get_attribute("id") == "main-content"
    page.get_by_label("用户名").fill(username)
    page.get_by_label("密码").fill(password)
    activate(page, page.get_by_role("button", name="登录"), interaction)
    page.wait_for_url(re.compile(r"/create/(?:#main-content)?$"))
    assert page.get_by_role("navigation", name="主导航").is_visible()

    _, _, image_bytes = next(build_demo_images())
    page.locator("input[type=file]").set_input_files(
        {"name": "e2e-person.png", "mimeType": "image/png", "buffer": image_bytes}
    )
    activate(page, page.get_by_role("button", name="上传并分析"), interaction)
    page.wait_for_url(re.compile(r"/analysis/(?:#main-content)?$"))
    page.get_by_role("heading", name="智能分析完成").wait_for()
    assert page.locator(".notice").count() <= 3

    confirm = page.get_by_role("link", name="确认生成设置")
    if confirm.count():
        activate(page, confirm, interaction)
    else:
        activate(page, page.get_by_role("link", name=re.compile("仍然继续")), interaction)
    page.wait_for_url(re.compile(r"/settings/(?:#main-content)?$"))
    page.get_by_label("图纸尺寸").select_option("30")
    page.get_by_label("颜色数量").select_option("12")
    page.get_by_label("背景处理").select_option("keep")
    activate(page, page.get_by_role("button", name="开始生成 1 张图纸"), interaction)
    page.wait_for_url(re.compile(r"/progress/(?:#main-content)?$"))
    activate(page, page.get_by_role("link", name="查看生成结果"), interaction)

    page.wait_for_url(re.compile(r"/result/(?:#main-content)?$"))
    page.get_by_role("heading", name="图纸已经生成").wait_for()
    tabs = page.get_by_role("tab")
    assert tabs.count() == 3
    effect_tab = page.get_by_role("tab", name="效果图")
    grid_tab = page.get_by_role("tab", name="网格图")
    materials_tab = page.get_by_role("tab", name="材料与建议")
    assert effect_tab.get_attribute("aria-selected") == "true"
    if interaction == "keyboard":
        effect_tab.focus()
        page.keyboard.press("End")
        assert materials_tab.evaluate("element => document.activeElement === element")
    else:
        materials_tab.click()
    assert materials_tab.get_attribute("aria-selected") == "true"
    assert page.get_by_role("tabpanel", name="材料与建议").is_visible()
    if interaction == "keyboard":
        page.keyboard.press("Home")
        page.keyboard.press("ArrowRight")
    else:
        grid_tab.click()
    assert grid_tab.get_attribute("aria-selected") == "true"
    assert page.get_by_role("tabpanel", name="网格图").is_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    activate(page, page.get_by_role("link", name="保存图纸"), interaction)
    page.get_by_label("图纸名称").fill(f"浏览器验收 {viewport['width']}")
    activate(page, page.get_by_role("button", name="确认保存"), interaction)

    page.wait_for_url(re.compile(r"/patterns/\d+/(?:#main-content)?$"))
    assert page.get_by_role("heading", name=f"浏览器验收 {viewport['width']}").is_visible()
    assert page.get_by_text("版本历史").is_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    close_main_journey_page(page, recording_context, recording_destination)


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-invalid-media")
def test_browser_rejects_damaged_upload_next_to_the_file_control(
    browser,
    live_server,
    django_user_model,
):
    page, user = signed_in_page(
        browser,
        live_server,
        django_user_model,
        "e2e-invalid-upload",
    )
    page.locator("input[type=file]").set_input_files(
        {"name": "damaged.png", "mimeType": "image/png", "buffer": b"not-an-image"}
    )

    page.get_by_role("button", name="上传并分析").click()

    assert page.url.endswith("/create/")
    assert page.locator(".upload-box .errorlist").is_visible()
    assert "请上传一张有效的" in page.locator(".upload-box .errorlist").inner_text()
    assert user.generation_tasks.count() == 0


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-subject-media")
def test_browser_reselects_an_uncertain_subject_without_reuploading(
    browser,
    live_server,
    django_user_model,
):
    page, user = signed_in_page(
        browser,
        live_server,
        django_user_model,
        "e2e-subject-selection",
    )
    output = BytesIO()
    Image.new("RGB", (32, 32), (128, 128, 128)).save(output, format="PNG")
    upload_for_analysis(page, output.getvalue(), filename="uncertain.png")

    assert page.get_by_text("适配结果：可以尝试").is_visible()
    page.get_by_label("主体左边界").fill("0.2")
    page.get_by_label("主体上边界").fill("0.2")
    page.get_by_label("主体宽度").fill("0.6")
    page.get_by_label("主体高度").fill("0.6")
    page.get_by_role("button", name="使用这个主体").click()
    page.wait_for_url(re.compile(r"/settings/$"))

    task = user.generation_tasks.get()
    task.analysis.refresh_from_db()
    assert task.analysis.requires_subject_confirmation is False
    assert task.analysis.subject_region == {"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6}


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-quota-media")
def test_browser_keeps_settings_when_generation_images_are_exhausted(
    browser,
    live_server,
    django_user_model,
):
    page, user = signed_in_page(
        browser,
        live_server,
        django_user_model,
        "e2e-no-quota",
    )
    quota = get_or_create_current_quota(user)
    quota.total_limit = 0
    quota.save(update_fields=("total_limit", "updated_at"))
    _, _, image_bytes = next(build_demo_images())
    upload_for_analysis(page, image_bytes)
    continue_to_settings(page)
    choose_basic_settings(page, size="70", colors="36", background="keep")

    page.get_by_role("button", name="开始生成 1 张图纸").click()

    assert re.search(r"/settings/$", page.url)
    assert page.get_by_text("你本周期的生成张数已经用完").is_visible()
    assert page.get_by_label("图纸尺寸").input_value() == "70"
    assert page.get_by_label("颜色数量").input_value() == "36"
    quota.refresh_from_db()
    assert (quota.used_count, quota.reserved_count) == (0, 0)


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-recovery-media")
def test_browser_explains_free_retry_and_recovers_from_save_failure(
    browser,
    live_server,
    django_user_model,
):
    page, user = signed_in_page(
        browser,
        live_server,
        django_user_model,
        "e2e-retry-save",
    )
    _, _, image_bytes = next(build_demo_images())
    upload_for_analysis(page, image_bytes)
    continue_to_settings(page)
    choose_basic_settings(page)
    attempts = 0

    def fail_once(task, settings):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary generation failure")
        return real_generate_basic_pattern(task, settings)

    with patch("apps.creation.tasks.generate_basic_pattern", side_effect=fail_once):
        page.get_by_role("button", name="开始生成 1 张图纸").click()
    page.wait_for_url(re.compile(r"/progress/$"))

    assert page.get_by_text("结果已经过 1 次免费自动优化").is_visible()
    assert page.get_by_text("没有重复计算张数").is_visible()
    task = user.generation_tasks.get()
    task.refresh_from_db()
    task.quota_period.refresh_from_db()
    assert attempts == 2
    assert task.retry_count == 1
    assert task.quota_period.used_count == 1
    assert (
        GenerationQuotaLedger.objects.filter(
            task_reference=task.id,
            event=QuotaLedgerEvent.RESERVE,
        ).count()
        == 1
    )
    assert (
        GenerationQuotaLedger.objects.filter(
            task_reference=task.id,
            event=QuotaLedgerEvent.CONSUME,
        ).count()
        == 1
    )

    page.get_by_role("link", name="查看生成结果").click()
    page.get_by_role("link", name="保存图纸").click()
    page.get_by_label("图纸名称").fill("保存恢复验收")
    with patch(
        "apps.patterns.models.Pattern.save",
        side_effect=DatabaseError("temporary database failure"),
    ):
        page.get_by_role("button", name="确认保存").click()

    assert page.get_by_text("作品暂时无法保存，请稍后重试").is_visible()
    task.refresh_from_db()
    assert task.status == GenerationStatus.SUCCEEDED
    assert task.result_version_id is not None

    page.get_by_role("button", name="确认保存").click()
    page.wait_for_url(re.compile(r"/patterns/\d+/$"))
    assert page.get_by_role("heading", name="保存恢复验收").is_visible()


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-failure-media")
def test_browser_shows_final_generation_failure_and_releases_reserved_image(
    browser,
    live_server,
    django_user_model,
):
    page, user = signed_in_page(
        browser,
        live_server,
        django_user_model,
        "e2e-generation-failure",
    )
    _, _, image_bytes = next(build_demo_images())
    upload_for_analysis(page, image_bytes)
    continue_to_settings(page)
    choose_basic_settings(page)

    with patch(
        "apps.creation.tasks.generate_basic_pattern",
        side_effect=RuntimeError("permanent generation failure"),
    ):
        page.get_by_role("button", name="开始生成 1 张图纸").click()
    page.wait_for_url(re.compile(r"/progress/$"))

    assert page.get_by_text("本次生成未完成，没有使用你的生成张数").is_visible()
    task = user.generation_tasks.get()
    task.refresh_from_db()
    task.quota_period.refresh_from_db()
    assert task.status == GenerationStatus.FAILED
    assert task.retry_count == 2
    assert (task.quota_period.used_count, task.quota_period.reserved_count) == (0, 0)
