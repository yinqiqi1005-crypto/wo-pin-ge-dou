import re

import pytest
from django.core.management import call_command
from django.test import override_settings

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
    page = browser.new_page(viewport=viewport)

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
    page.close()
