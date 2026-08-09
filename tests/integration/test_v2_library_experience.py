import pytest

from apps.patterns.models import Pattern, PatternCategory, PatternVersion

pytestmark = pytest.mark.django_db


def test_library_filters_saved_patterns_by_the_users_category(client, django_user_model):
    user = django_user_model.objects.create_user(username="library-category-user")
    portrait = PatternCategory.objects.get(owner=user, name="人物")
    pet = PatternCategory.objects.get(owner=user, name="宠物")
    Pattern.objects.create(owner=user, title="人物图纸", category=portrait, is_saved=True)
    Pattern.objects.create(owner=user, title="宠物图纸", category=pet, is_saved=True)
    client.force_login(user)

    response = client.get(f"/patterns/?category={portrait.pk}")

    page = response.content.decode()
    assert response.status_code == 200
    assert "人物图纸" in page
    assert "宠物图纸" not in page
    assert 'aria-current="page"' in page


def test_saved_pattern_detail_shows_the_ironing_style_chosen_by_the_user(client, django_user_model):
    user = django_user_model.objects.create_user(username="library-ironing-user")
    pattern = Pattern.objects.create(owner=user, title="杯垫", is_saved=True)
    PatternVersion.objects.create(
        pattern=pattern,
        version_number=1,
        grid_data={"width": 58, "height": 58},
        settings_snapshot={"ironing_style": "flat_melt"},
    )
    client.force_login(user)

    response = client.get(f"/patterns/{pattern.pk}/")

    page = response.content.decode()
    assert response.status_code == 200
    assert "你选择的烫豆方式" in page
    assert "平烫全熔" in page
    assert "新手操作说明" in page
