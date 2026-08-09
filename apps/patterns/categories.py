from .models import DefaultPatternCategory, PatternCategory

DEFAULT_CATEGORIES = (
    ("people", "人物", 10, False),
    ("pets", "宠物", 20, False),
    ("anime", "动漫", 30, False),
    ("objects", "物品", 40, False),
    ("scenery", "风景", 50, False),
    ("text", "文字", 60, False),
    ("other", "其他", 70, True),
)


def ensure_default_category_templates():
    for code, name, sort_order, is_fallback in DEFAULT_CATEGORIES:
        DefaultPatternCategory.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_fallback": is_fallback,
                "is_active": True,
            },
        )


def ensure_user_categories(user):
    categories = PatternCategory.objects.filter(owner=user)
    if categories.exists():
        return categories
    ensure_default_category_templates()
    templates = DefaultPatternCategory.objects.filter(is_active=True).order_by("sort_order", "code")
    PatternCategory.objects.bulk_create(
        [
            PatternCategory(
                owner=user,
                name=template.name,
                sort_order=template.sort_order,
                is_fallback=template.is_fallback,
            )
            for template in templates
        ]
    )
    return PatternCategory.objects.filter(owner=user)


def fallback_category_for_user(user):
    ensure_user_categories(user)
    fallback = PatternCategory.objects.filter(owner=user, is_fallback=True).first()
    if fallback:
        return fallback
    return PatternCategory.objects.create(owner=user, name="其他", sort_order=999, is_fallback=True)
