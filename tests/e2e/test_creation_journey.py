import re

import pytest
from django.core.management import call_command
from django.test import override_settings

from services.demo_assets import build_demo_images

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 1280, "height": 900},
        {"width": 390, "height": 844},
    ],
    ids=("desktop", "mobile"),
)
@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-e2e-media")
def test_real_browser_completes_six_step_creation_and_save(
    browser, live_server, django_user_model, viewport
):
    call_command("seed_demo_config", verbosity=0)
    username = f"e2e-{viewport['width']}"
    password = "E2E-safe-password"
    django_user_model.objects.create_user(username=username, password=password)
    page = browser.new_page(viewport=viewport)

    page.goto(f"{live_server.url}/accounts/login/")
    page.get_by_label("用户名").fill(username)
    page.get_by_label("密码").fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(re.compile(r"/create/$"))

    _, _, image_bytes = next(build_demo_images())
    page.locator("input[type=file]").set_input_files(
        {"name": "e2e-person.png", "mimeType": "image/png", "buffer": image_bytes}
    )
    page.get_by_role("button", name="上传并分析").click()
    page.wait_for_url(re.compile(r"/analysis/$"))
    page.get_by_role("heading", name="智能分析完成").wait_for()
    assert page.locator(".notice").count() <= 3

    confirm = page.get_by_role("link", name="确认生成设置")
    if confirm.count():
        confirm.click()
    else:
        page.get_by_role("link", name=re.compile("仍然继续")).click()
    page.wait_for_url(re.compile(r"/settings/$"))
    page.get_by_label("图纸尺寸").select_option("30")
    page.get_by_label("颜色数量").select_option("12")
    page.get_by_label("背景处理").select_option("keep")
    page.get_by_role("button", name="开始生成 1 张图纸").click()
    page.wait_for_url(re.compile(r"/progress/$"))
    page.get_by_role("link", name="查看生成结果").click()

    page.wait_for_url(re.compile(r"/result/$"))
    page.get_by_role("heading", name="图纸已经生成").wait_for()
    assert page.get_by_text("材料与建议").is_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    page.get_by_role("link", name="保存图纸").click()
    page.get_by_label("图纸名称").fill(f"浏览器验收 {viewport['width']}")
    page.get_by_role("button", name="确认保存").click()

    page.wait_for_url(re.compile(r"/patterns/\d+/$"))
    assert page.get_by_role("heading", name=f"浏览器验收 {viewport['width']}").is_visible()
    assert page.get_by_text("版本历史").is_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )
    page.close()
