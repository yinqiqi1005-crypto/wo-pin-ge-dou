from apps.creation.ironing import IRONING_STYLES, get_ironing_style


def test_standard_two_sided_style_is_the_hole_preserving_baseline():
    style = get_ironing_style("standard_two_sided")

    assert style["code"] == "standard_two_sided"
    assert "双面" in style["name"]
    assert "豆孔" in style["effect"]


def test_ironing_styles_are_choices_not_a_use_based_recommendation():
    codes = set(IRONING_STYLES)

    assert codes == {
        "standard_two_sided",
        "single_sided_shape",
        "flat_melt",
        "large_project_tape",
    }


def test_unknown_style_uses_the_safe_standard_reference():
    style = get_ironing_style("unknown")

    assert style["code"] == "standard_two_sided"
