from apps.creation.services import face_detail_check


def test_face_detail_check_warns_but_never_blocks_small_portraits():
    result = face_detail_check(
        {"grid_width": 29, "grid_height": 29, "face_mode": "face_detail"}
    )

    assert result["status"] == "warning"
    assert "58×58" in result["message"]


def test_face_detail_check_confirms_detail_protection_at_recommended_size():
    result = face_detail_check(
        {"grid_width": 58, "grid_height": 87, "face_mode": "face_detail"}
    )

    assert result["status"] == "ready"
