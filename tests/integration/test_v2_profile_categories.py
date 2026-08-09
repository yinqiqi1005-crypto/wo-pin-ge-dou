import pytest
from django.urls import reverse

from apps.patterns.models import DefaultPatternCategory, Pattern, PatternCategory


@pytest.mark.django_db
def test_new_user_receives_editable_default_categories(django_user_model):
    user = django_user_model.objects.create_user(username="category-owner")

    categories = list(PatternCategory.objects.filter(owner=user).order_by("sort_order"))

    assert [category.name for category in categories] == [
        "人物",
        "宠物",
        "动漫",
        "物品",
        "风景",
        "文字",
        "其他",
    ]
    assert categories[-1].is_fallback is True


@pytest.mark.django_db
def test_deleting_category_moves_owned_patterns_to_fallback(django_user_model):
    user = django_user_model.objects.create_user(username="category-delete-owner")
    category = PatternCategory.objects.get(owner=user, name="人物")
    fallback = PatternCategory.objects.get(owner=user, is_fallback=True)
    pattern = Pattern.objects.create(owner=user, title="我的头像", category=category)

    category.delete()
    pattern.refresh_from_db()

    assert pattern.category_id == fallback.id


@pytest.mark.django_db
def test_template_change_only_applies_to_users_created_after_change(django_user_model):
    existing_user = django_user_model.objects.create_user(username="existing-category-user")
    template = DefaultPatternCategory.objects.get(code="people")
    template.name = "肖像"
    template.save(update_fields=("name", "updated_at"))
    new_user = django_user_model.objects.create_user(username="new-category-user")

    assert (
        PatternCategory.objects.get(owner=existing_user, sort_order=template.sort_order).name
        == "人物"
    )
    assert (
        PatternCategory.objects.get(owner=new_user, sort_order=template.sort_order).name == "肖像"
    )


@pytest.mark.django_db
def test_profile_and_creation_preferences_are_saved_per_user(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="profile-owner", password="safe-password-123"
    )
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile"),
        {
            "display_name": "阿布的拼豆工坊",
            "email": "abo@example.com",
            "bio": "喜欢做人物拼豆。",
            "preferred_language": "ja",
            "default_pattern_size": "58x58",
            "default_color_limit": 24,
            "default_background_mode": "simplify",
            "default_finished_use": "display",
            "remember_creation_parameters": "on",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    profile = user.profile
    assert profile.display_name == "阿布的拼豆工坊"
    assert user.email == "abo@example.com"
    assert profile.bio == "喜欢做人物拼豆。"
    assert profile.preferred_language == "ja"
    assert profile.default_pattern_size == "58x58"
    assert profile.remember_creation_parameters is True


@pytest.mark.django_db
def test_profile_page_is_private_and_contains_language_and_category_entries(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="profile-page-user", password="safe-password-123"
    )
    url = reverse("accounts:profile")

    assert client.get(url).status_code == 302
    client.force_login(user)
    response = client.get(url)

    assert response.status_code == 200
    page = response.content.decode()
    assert "个人资料与设置" in page
    assert "界面语言" in page
    assert "我的分类" in page


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("language", "expected"),
    (("en", "AI creation"), ("ja", "AI作成"), ("ko", "AI 만들기")),
)
def test_saved_language_preference_translates_frontend_navigation(
    client, django_user_model, language, expected
):
    user = django_user_model.objects.create_user(
        username=f"language-{language}", password="safe-password-123"
    )
    client.force_login(user)
    profile = user.profile
    profile.preferred_language = language
    profile.save(update_fields=("preferred_language", "updated_at"))

    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 200
    assert expected in response.content.decode()


@pytest.mark.django_db
def test_user_can_add_rename_and_delete_only_own_categories(client, django_user_model):
    owner = django_user_model.objects.create_user(
        username="category-manager", password="safe-password-123"
    )
    stranger = django_user_model.objects.create_user(
        username="category-stranger", password="safe-password-123"
    )
    client.force_login(owner)

    added = client.post(reverse("accounts:add_category"), {"name": "旅行", "sort_order": 5})
    assert added.status_code == 302
    category = PatternCategory.objects.get(owner=owner, name="旅行")

    updated = client.post(
        reverse("accounts:update_category", args=(category.pk,)),
        {"name": "旅行纪念", "sort_order": 3},
    )
    assert updated.status_code == 302
    category.refresh_from_db()
    assert (category.name, category.sort_order) == ("旅行纪念", 3)

    other_category = PatternCategory.objects.get(owner=stranger, name="人物")
    assert (
        client.post(
            reverse("accounts:update_category", args=(other_category.pk,)),
            {"name": "不应更新", "sort_order": 1},
        ).status_code
        == 404
    )

    assert client.post(reverse("accounts:delete_category", args=(category.pk,))).status_code == 302
    assert not PatternCategory.objects.filter(pk=category.pk).exists()
