import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.operations.release_performance import (
    ReleasePerformanceError,
    measure_stage,
    run_release_performance,
)


class SequenceClock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def test_measure_stage_uses_every_sample_and_preserves_strict_limit():
    calls = []

    _, stage = measure_stage(
        "sample",
        lambda: calls.append("called"),
        iterations=3,
        limit_seconds=1.0,
        clock=SequenceClock((0.0, 0.2, 1.0, 1.4, 2.0, 2.8)),
    )

    assert calls == ["called", "called", "called"]
    assert stage.samples_seconds == (0.2, 0.4, 0.8)
    assert stage.median_seconds == 0.4
    assert stage.maximum_seconds == 0.8


def test_measure_stage_rejects_result_above_limit_without_rounding_it_down():
    with pytest.raises(ReleasePerformanceError, match="limit is 1.000s"):
        measure_stage(
            "slow",
            lambda: None,
            iterations=1,
            limit_seconds=1.0,
            clock=SequenceClock((0.0, 1.000001)),
        )


@pytest.mark.parametrize("iterations", [0, 11])
def test_measure_stage_rejects_invalid_iteration_count(iterations):
    with pytest.raises(ReleasePerformanceError, match="between 1 and 10"):
        measure_stage(
            "sample",
            lambda: None,
            iterations=iterations,
            limit_seconds=1.0,
        )


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-performance-test-media")
def test_real_release_performance_runs_every_required_stage():
    report = run_release_performance(iterations=1)

    assert [stage.name for stage in report.stages] == [
        "upload_storage",
        "rule_analysis",
        "pattern_generation",
        "pdf_export",
    ]
    assert report.sample["grid_size"] == 70
    assert report.sample["color_limit"] == 36
    assert report.sample["effect_png_bytes"] > 0
    assert report.sample["grid_png_bytes"] > 0
    assert all(stage.maximum_seconds <= stage.limit_seconds for stage in report.stages)


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-performance-command-media")
def test_performance_command_saves_non_overwriting_json_evidence(tmp_path):
    report_path = tmp_path / "performance.json"

    call_command(
        "check_release_performance",
        report=report_path,
        iterations=1,
        verbosity=0,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["iterations"] == 1
    assert len(payload["stages"]) == 4
    assert payload["sample"]["grid_size"] == 70
    with pytest.raises(CommandError):
        call_command(
            "check_release_performance",
            report=report_path,
            iterations=1,
            verbosity=0,
        )
