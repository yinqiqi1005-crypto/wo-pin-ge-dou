import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from statistics import median
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw

from services.ai.providers.rules import RuleBasedAnalysisProvider
from services.exports import render_pattern_pdf
from services.image_processing import (
    create_pattern,
    render_effect_preview,
    render_grid_preview,
)


class ReleasePerformanceError(ValueError):
    pass


@dataclass(frozen=True)
class StagePerformance:
    name: str
    samples_seconds: tuple[float, ...]
    median_seconds: float
    maximum_seconds: float
    limit_seconds: float


@dataclass(frozen=True)
class ReleasePerformanceReport:
    checked_at: str
    python_version: str
    platform: str
    iterations: int
    sample: dict
    stages: tuple[StagePerformance, ...]


PERFORMANCE_LIMITS = {
    "upload_storage": 2.0,
    "rule_analysis": 2.0,
    "pattern_generation": 10.0,
    "pdf_export": 10.0,
}


def measure_stage(name, operation, *, iterations, limit_seconds, clock=monotonic):
    if not 1 <= iterations <= 10:
        raise ReleasePerformanceError("Performance iterations must be between 1 and 10.")
    samples = []
    result = None
    for _ in range(iterations):
        started = clock()
        result = operation()
        samples.append(clock() - started)
    maximum = max(samples)
    stage = StagePerformance(
        name=name,
        samples_seconds=tuple(round(value, 6) for value in samples),
        median_seconds=round(median(samples), 6),
        maximum_seconds=round(maximum, 6),
        limit_seconds=limit_seconds,
    )
    if maximum > limit_seconds:
        raise ReleasePerformanceError(f"{name} took {maximum:.3f}s; limit is {limit_seconds:.3f}s.")
    return result, stage


def _sample_image_bytes():
    image = Image.new("RGB", (800, 600), (239, 231, 218))
    draw = ImageDraw.Draw(image)
    draw.ellipse((190, 70, 610, 490), fill=(192, 115, 82), outline=(70, 49, 45), width=18)
    draw.ellipse((285, 210, 340, 265), fill=(35, 33, 38))
    draw.ellipse((460, 210, 515, 265), fill=(35, 33, 38))
    draw.arc((320, 235, 480, 380), start=15, end=165, fill=(92, 42, 49), width=14)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _image_png_bytes(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def run_release_performance(*, iterations=3, storage=None, now=None):
    storage = storage or default_storage
    image_bytes = _sample_image_bytes()
    stages = []
    stored_names = []

    def upload_storage_round_trip():
        name = f"performance-check/{uuid4()}.png"
        stored_name = storage.save(name, ContentFile(image_bytes))
        stored_names.append(stored_name)
        try:
            with storage.open(stored_name, "rb") as source:
                restored = source.read()
            if restored != image_bytes:
                raise ReleasePerformanceError("Stored upload bytes changed during round trip.")
        finally:
            storage.delete(stored_name)
            stored_names.remove(stored_name)

    try:
        _, stage = measure_stage(
            "upload_storage",
            upload_storage_round_trip,
            iterations=iterations,
            limit_seconds=PERFORMANCE_LIMITS["upload_storage"],
        )
        stages.append(stage)

        provider = RuleBasedAnalysisProvider()

        def analyze():
            result = provider.analyze(image_bytes, media_type="image/png")
            if not result.analysis.primary_subject:
                raise ReleasePerformanceError("Rule analysis returned no subject.")
            return result

        _, stage = measure_stage(
            "rule_analysis",
            analyze,
            iterations=iterations,
            limit_seconds=PERFORMANCE_LIMITS["rule_analysis"],
        )
        stages.append(stage)

        def generate():
            result = create_pattern(BytesIO(image_bytes), size=70, color_limit=36)
            effect = render_effect_preview(result.grid, palette=result.palette)
            grid = render_grid_preview(result.grid, palette=result.palette)
            return result, _image_png_bytes(effect), _image_png_bytes(grid)

        generated, stage = measure_stage(
            "pattern_generation",
            generate,
            iterations=iterations,
            limit_seconds=PERFORMANCE_LIMITS["pattern_generation"],
        )
        stages.append(stage)
        pattern_result, effect_bytes, grid_bytes = generated

        def export_pdf():
            version = SimpleNamespace(
                pattern=SimpleNamespace(title="性能验收图纸"),
                version_number=1,
                grid_data={
                    "width": pattern_result.grid.width,
                    "height": pattern_result.grid.height,
                    "cells": pattern_result.grid.cells,
                },
                material_counts=pattern_result.material_counts,
                total_beads=sum(pattern_result.material_counts.values()),
                effect_preview=ContentFile(effect_bytes, name="effect.png"),
            )
            content, page_count, _ = render_pattern_pdf(
                version,
                guidance={
                    "difficulty": "进阶",
                    "advice": "建议分区制作并逐区核对坐标。",
                },
            )
            if not content.startswith(b"%PDF") or page_count < 6:
                raise ReleasePerformanceError("PDF export did not produce a complete document.")
            return content

        _, stage = measure_stage(
            "pdf_export",
            export_pdf,
            iterations=iterations,
            limit_seconds=PERFORMANCE_LIMITS["pdf_export"],
        )
        stages.append(stage)
    finally:
        for stored_name in stored_names:
            storage.delete(stored_name)

    checked_at = now or datetime.now(UTC)
    return ReleasePerformanceReport(
        checked_at=checked_at.isoformat(),
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.machine()}",
        iterations=iterations,
        sample={
            "image_width": 800,
            "image_height": 600,
            "grid_size": 70,
            "color_limit": 36,
            "effect_png_bytes": len(effect_bytes),
            "grid_png_bytes": len(grid_bytes),
        },
        stages=tuple(stages),
    )


def save_release_performance_report(report, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    payload["runtime"] = {"python_executable": Path(sys.executable).name}
    with destination.open("x", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")
