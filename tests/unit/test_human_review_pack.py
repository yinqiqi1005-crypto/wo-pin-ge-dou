import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from apps.operations.human_review import HumanReviewPackError, build_human_review_pack

RESULTS_PATH = Path(__file__).parents[2] / "docs" / "test-results-40.csv"


def test_human_review_pack_contains_all_sources_effects_grids_and_manifest_data(tmp_path):
    destination = build_human_review_pack(
        tmp_path / "review-round-1",
        results_path=RESULTS_PATH,
    )

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    html = (destination / "index.html").read_text(encoding="utf-8")
    assert manifest["case_count"] == 40
    assert len(manifest["cases"]) == 40
    assert html.count('<article class="case"') == 40
    assert "本页面不自动判定人工指标" in html

    for entry in manifest["cases"]:
        assert entry["case_id"] in html
        assert entry["human_review"] == "pending"
        assert entry["material_consistency"] == "pass"
        assert entry["actual_color_count"] <= entry["color_limit"]
        assert 0 < entry["total_beads"] <= entry["grid_size"] ** 2
        for kind in ("source", "effect", "grid"):
            image_path = destination / entry[f"{kind}_file"]
            assert image_path.is_file()
            assert len(entry["sha256"][kind]) == 64
            with Image.open(image_path) as image:
                image.verify()
        with Image.open(destination / entry["effect_file"]) as effect:
            assert effect.size == (entry["grid_size"] * 12,) * 2
        with Image.open(destination / entry["grid_file"]) as grid:
            expected_grid_pixels = entry["grid_size"] * 24 + 1
            assert grid.size == (expected_grid_pixels, expected_grid_pixels)

    assert len(list((destination / "sources").glob("*.png"))) == 40
    assert len(list((destination / "effects").glob("*.png"))) == 40
    assert len(list((destination / "grids").glob("*.png"))) == 40


def test_human_review_pack_never_overwrites_an_existing_review_round(tmp_path):
    destination = tmp_path / "existing-review"
    destination.mkdir()
    marker = destination / "reviewer-notes.txt"
    marker.write_text("keep", encoding="utf-8")

    with (
        patch("apps.operations.human_review.build_case_image") as build_image,
        pytest.raises(HumanReviewPackError, match="already exists"),
    ):
        build_human_review_pack(destination, results_path=RESULTS_PATH)

    build_image.assert_not_called()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_human_review_pack_rejects_an_incomplete_results_table_before_generation(tmp_path):
    incomplete = tmp_path / "incomplete.csv"
    lines = RESULTS_PATH.read_text(encoding="utf-8").splitlines()
    incomplete.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    with (
        patch("apps.operations.human_review.build_case_image") as build_image,
        pytest.raises(HumanReviewPackError, match="exactly the fixed 40 cases"),
    ):
        build_human_review_pack(
            tmp_path / "review-round",
            results_path=incomplete,
        )

    build_image.assert_not_called()
