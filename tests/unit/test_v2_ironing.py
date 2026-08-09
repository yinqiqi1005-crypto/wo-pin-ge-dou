from apps.creation.ironing import recommend_ironing_method


def test_daily_use_recommends_durable_double_sided_ironing():
    recommendation = recommend_ironing_method("daily", width=58, height=58)

    assert recommendation["code"] == "double_sided"
    assert "牢固" in recommendation["reason"]


def test_display_recommends_hole_preserving_light_ironing():
    recommendation = recommend_ironing_method("display", width=87, height=87)

    assert recommendation["code"] == "light_single"
    assert "豆孔" in recommendation["reason"]


def test_unsure_large_pattern_gets_clear_default_without_blocking_choice():
    recommendation = recommend_ironing_method("unsure", width=116, height=116)

    assert recommendation["code"] == "standard_single"
    assert recommendation["alternatives"]
