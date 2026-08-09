from pathlib import Path

import pytest

from apps.creation.ironing import IRONING_STYLES
from apps.patterns.models import Pattern, PatternVersion

pytestmark = pytest.mark.django_db


def test_each_ironing_style_has_a_real_case_image_and_source_link():
    assert set(IRONING_STYLES) == {
        "waffle", "regular", "towel", "bathcloth", "baking_paper", "glitter"
    }
    for style in IRONING_STYLES.values():
        assert style["case_image_url"].startswith("https://")
        assert style["source_url"].startswith("https://")
        assert style["case_source_url"].startswith("https://")
        assert style["case_source_label"]
        assert style.get("case_is_ai_generated", False) is False


def test_library_report_shows_a_style_specific_3d_model(client, django_user_model):
    user = django_user_model.objects.create_user(username="report-user")
    pattern = Pattern.objects.create(owner=user, title="科技报告", is_saved=True)
    PatternVersion.objects.create(
        pattern=pattern,
        version_number=1,
        grid_data={"width": 58, "height": 58},
        material_counts={"WPD-001": 100},
        settings_snapshot={"ironing_style": "glitter"},
    )
    client.force_login(user)

    response = client.get(f"/patterns/{pattern.pk}/")

    page = response.content.decode()
    assert response.status_code == 200
    assert "拼豆制作报告" in page
    assert "data-bead-model" in page
    assert "glitter" in page
    assert "真实案例图片" in page
    assert 'href="https://' not in page


def test_report_uses_the_active_theme_surface_with_a_lightweight_data_grid():
    css = Path("static/css/app.css").read_text()

    assert ".bead-report" in css
    assert "background: linear-gradient(color-mix(in srgb, var(--surface)" in css
    assert "border: 1px solid var(--line)" in css
    assert "background-size: auto, 24px 24px, 24px 24px, auto" in css


def test_library_can_rename_delete_and_restore_without_opening_detail(client, django_user_model):
    user = django_user_model.objects.create_user(username="library-fast-user")
    pattern = Pattern.objects.create(owner=user, title="旧名称", is_saved=True)
    client.force_login(user)

    renamed = client.post(
        f"/patterns/{pattern.pk}/update/",
        {"title": "新名称"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    pattern.refresh_from_db()
    deleted = client.post(
        f"/patterns/{pattern.pk}/delete/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    pattern.refresh_from_db()
    assert pattern.deleted_at is not None
    trash_page = client.get("/patterns/?view=trash")
    restored = client.post(
        f"/patterns/{pattern.pk}/restore/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    pattern.refresh_from_db()

    assert renamed.json() == {"renamed": True, "title": "新名称"}
    assert deleted.json() == {"deleted": True}
    assert "新名称" in trash_page.content.decode()
    assert restored.json() == {"restored": True}
    assert pattern.deleted_at is None


def test_library_hides_inline_rename_form_until_the_user_clicks_edit(client, django_user_model):
    user = django_user_model.objects.create_user(username="library-rename-visibility")
    Pattern.objects.create(owner=user, title="默认隐藏", is_saved=True)
    client.force_login(user)

    page = client.get("/patterns/").content.decode()

    assert 'data-inline-rename hidden' in page
    assert ".inline-rename-form[hidden] { display: none; }" in Path(
        "static/css/app.css"
    ).read_text()


def test_header_groups_language_and_account_settings(client, django_user_model):
    user = django_user_model.objects.create_user(username="header-user")
    client.force_login(user)

    page = client.get("/").content.decode()

    assert "data-language-picker" in page
    assert "data-account-menu" in page
    assert "个人资料与设置" in page
    assert 'href="/accounts/profile/">设置' not in page
