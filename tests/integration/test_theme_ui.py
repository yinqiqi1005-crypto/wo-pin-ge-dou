import pytest

pytestmark = pytest.mark.django_db


def test_home_exposes_four_persistent_visual_themes(client):
    response = client.get("/")
    content = response.content.decode()

    assert response.status_code == 200
    assert content.count("data-theme-choice=") == 4
    assert 'aria-expanded="false"' in content
    assert 'id="theme-menu"' in content
    assert "app.css?v=20260809-v27" in content
    assert "creation.js?v=20260809-v27" in content
    for theme in ("garden", "night", "paper", "pixel"):
        assert f'data-theme-choice="{theme}"' in content
    assert 'localStorage.setItem("wpgd-theme", theme)' in content or "wpgd-theme" in content


def test_home_keeps_creation_entry_and_visual_theme_labels(client):
    content = client.get("/").content.decode()

    assert "开始创作" in content
    for label in ("豆豆乐园", "像素夜", "纸张工坊", "像素可爱"):
        assert label in content
