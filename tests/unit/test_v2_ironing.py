from apps.creation.ironing import IRONING_STYLES, get_ironing_style


def test_regular_style_is_the_safe_beginner_baseline():
    style = get_ironing_style("regular")

    assert style["code"] == "regular"
    assert "常规" in style["name"]
    assert "第一次" in style["best_for"]


def test_ironing_styles_are_choices_not_a_use_based_recommendation():
    codes = set(IRONING_STYLES)

    assert codes == {
        "waffle",
        "regular",
        "towel",
        "bathcloth",
        "baking_paper",
        "glitter",
    }


def test_unknown_style_uses_the_safe_standard_reference():
    style = get_ironing_style("unknown")

    assert style["code"] == "regular"
