from io import BytesIO
from time import monotonic

import numpy as np
from PIL import Image, ImageStat, UnidentifiedImageError

from services.ai.prompts import ANALYSIS_PROMPT_VERSION
from services.ai.schemas import AnalysisRecommendation, ImageAnalysis, SubjectRegion

from .base import AnalysisProviderResult


class RuleBasedAnalysisProvider:
    provider_name = "rules"
    model_name = "rule-analysis-v1"

    def __init__(
        self,
        *,
        grid_sizes=(30, 50, 70),
        color_limits=(12, 24, 36),
        background_modes=("keep", "simplify", "remove"),
    ):
        if not grid_sizes or not color_limits or not background_modes:
            raise ValueError("At least one generation option must be enabled.")
        self.grid_sizes = tuple(sorted(grid_sizes))
        self.color_limits = tuple(sorted(color_limits))
        self.background_modes = tuple(background_modes)

    def analyze(self, image_bytes: bytes, *, media_type: str) -> AnalysisProviderResult:
        started = monotonic()
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Uploaded image cannot be analyzed.") from exc

        width, height = image.size
        gray = image.convert("L")
        brightness = ImageStat.Stat(gray).mean[0]
        contrast = ImageStat.Stat(gray).stddev[0]
        issues: list[str] = []
        quality = "good"

        if min(width, height) < 64:
            quality = "poor"
            issues.append("图片尺寸较小，细节可能丢失。")
        if brightness < 35:
            quality = "poor"
            issues.append("图片整体偏暗，主体细节不易辨认。")
        elif brightness > 235:
            quality = "usable" if quality == "good" else quality
            issues.append("图片整体偏亮，浅色细节可能丢失。")
        if contrast < 12:
            quality = "poor"
            issues.append("主体与背景对比度较低。")

        edge_variance = float(np.asarray(gray.resize((32, 32))).var())
        suitability = "suitable"
        if quality == "poor" or edge_variance < 20:
            suitability = "try"
        ideal_size = 70 if min(width, height) >= 700 else 50 if min(width, height) >= 64 else 30
        grid_size = min(self.grid_sizes, key=lambda value: abs(value - ideal_size))
        ideal_colors = 12 if grid_size == 30 else 24 if grid_size == 50 else 36
        color_limit = min(self.color_limits, key=lambda value: abs(value - ideal_colors))
        background_mode = (
            "simplify" if "simplify" in self.background_modes else self.background_modes[0]
        )
        analysis = ImageAnalysis(
            quality_level=quality,
            suitability_level=suitability,
            primary_subject="图片中央主体",
            subject_count=1,
            subject_region=SubjectRegion(x=0.1, y=0.1, width=0.8, height=0.8),
            confidence_level="low" if suitability == "try" else "medium",
            issues=issues[:3],
            recommendations=AnalysisRecommendation(
                grid_size=grid_size,
                color_limit=color_limit,
                background_mode=background_mode,
                reason=f"{grid_size}×{grid_size} 能兼顾当前图片细节和制作难度。",
            ),
            requires_subject_confirmation=suitability != "suitable",
        )
        return AnalysisProviderResult(
            analysis=analysis,
            provider=self.provider_name,
            model_name=self.model_name,
            prompt_version=ANALYSIS_PROMPT_VERSION,
            latency_ms=max(1, int((monotonic() - started) * 1000)),
        )
