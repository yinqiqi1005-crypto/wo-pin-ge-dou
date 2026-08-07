import logging
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw
from pydantic import ValidationError

from services.ai import get_analysis_provider
from services.ai.providers.rules import RuleBasedAnalysisProvider

from .models import (
    GenerationStatus,
    GenerationTask,
    ImageAnalysisResult,
    ModelCallLog,
    ModelCapability,
)
from .state import transition_task

logger = logging.getLogger(__name__)


def _record_call(
    task,
    result=None,
    *,
    provider="",
    model_name="",
    error=None,
    retry=0,
    internal_cost=None,
):
    ModelCallLog.objects.create(
        task=task,
        capability=ModelCapability.ANALYSIS,
        provider=result.provider if result else provider,
        model_name=result.model_name if result else model_name,
        prompt_version=result.prompt_version if result else "analysis-v1.0",
        latency_ms=result.latency_ms if result else 0,
        success=error is None,
        retry_number=retry,
        internal_cost=(
            internal_cost if internal_cost is not None else result.internal_cost if result else 0
        ),
        error_type=type(error).__name__ if error else "",
    )


def _save_subject_mask(analysis_record, image_bytes, region):
    with Image.open(BytesIO(image_bytes)) as source:
        mask = Image.new("L", source.size, 0)
    x = round(region.x * mask.width)
    y = round(region.y * mask.height)
    right = round((region.x + region.width) * mask.width)
    bottom = round((region.y + region.height) * mask.height)
    ImageDraw.Draw(mask).rectangle((x, y, right, bottom), fill=255)
    output = BytesIO()
    mask.save(output, format="PNG")
    analysis_record.subject_mask.save(
        f"task-{analysis_record.task_id}-subject.png",
        ContentFile(output.getvalue()),
        save=False,
    )


def _persist_result(task, result, image_bytes):
    analysis = result.analysis
    record, _ = ImageAnalysisResult.objects.update_or_create(
        task=task,
        defaults={
            "quality_level": analysis.quality_level,
            "suitability_level": analysis.suitability_level,
            "primary_subject": analysis.primary_subject,
            "subject_count": analysis.subject_count,
            "subject_region": analysis.subject_region.model_dump(),
            "confidence_level": analysis.confidence_level,
            "issues": analysis.issues,
            "recommendations": analysis.recommendations.model_dump(),
            "requires_subject_confirmation": analysis.requires_subject_confirmation,
            "model_name": result.model_name,
            "prompt_version": result.prompt_version,
        },
    )
    if analysis.requires_subject_confirmation or analysis.subject_count > 1:
        _save_subject_mask(record, image_bytes, analysis.subject_region)
    record.save()
    return record


def execute_analysis_task(task_id: str) -> GenerationTask:
    task = GenerationTask.objects.get(pk=task_id)
    if task.status == GenerationStatus.AWAITING_CONFIRMATION and hasattr(task, "analysis"):
        return task
    if task.status == GenerationStatus.UPLOADED:
        transition_task(
            task,
            GenerationStatus.ANALYZING,
            stage="image_analysis",
            message="正在识别主体并评估图片。",
        )
    if task.status != GenerationStatus.ANALYZING:
        raise ValueError(f"Task {task.pk} cannot be analyzed from status {task.status}.")
    if not task.input_image:
        raise ValueError("Generation task has no input image.")

    with task.input_image.open("rb") as source:
        image_bytes = source.read()
    extension = task.input_image.name.rsplit(".", 1)[-1].lower()
    media_type = "image/png" if extension == "png" else "image/jpeg"

    route = {
        **task.configuration_snapshot.get("model_routes", {}).get("analysis", {}),
        **task.configuration_snapshot.get("generation", {}).get("enabled_options", {}),
    }
    configured_provider = route.get("provider", settings.AI_ANALYSIS_PROVIDER).lower()
    configured_model = route.get("model", settings.AI_ANALYSIS_MODEL)
    provider = None
    try:
        provider = get_analysis_provider(route)
    except Exception as exc:
        logger.warning(
            "Analysis provider configuration failed",
            extra={"error_type": type(exc).__name__},
        )
        _record_call(
            task,
            provider=configured_provider,
            model_name=configured_model,
            error=exc,
        )

    result = None
    if provider is not None:
        configured_attempts = route.get("max_attempts", settings.AI_ANALYSIS_MAX_ATTEMPTS)
        max_attempts = 1 if configured_provider == "rules" else max(1, min(configured_attempts, 3))
        for retry in range(max_attempts):
            try:
                result = provider.analyze(image_bytes, media_type=media_type)
                _record_call(
                    task,
                    result,
                    internal_cost=route.get("simulated_cost_per_call", 0),
                )
                break
            except Exception as exc:
                _record_call(
                    task,
                    provider=provider.provider_name,
                    model_name=provider.model_name,
                    error=exc,
                    retry=retry,
                )
                if isinstance(exc, (ValidationError, ValueError, TypeError, KeyError)):
                    break
                logger.warning(
                    "Analysis provider attempt failed",
                    extra={"error_type": type(exc).__name__},
                )

    if result is None and configured_provider != "rules":
        fallback = RuleBasedAnalysisProvider(
            grid_sizes=tuple(route.get("grid_sizes", (30, 50, 70))),
            color_limits=tuple(route.get("color_limits", (12, 24, 36))),
            background_modes=tuple(route.get("background_modes", ("keep", "simplify", "remove"))),
        )
        try:
            result = fallback.analyze(image_bytes, media_type=media_type)
            _record_call(task, result)
        except Exception as exc:
            _record_call(
                task,
                provider=fallback.provider_name,
                model_name=fallback.model_name,
                error=exc,
            )

    if result is None:
        task.status = GenerationStatus.FAILED
        task.current_stage = "analysis_failed"
        task.failure_code = "AnalysisUnavailable"
        task.failure_message = "图片分析暂时不可用，请重新上传或稍后再试。"
        task.progress_message = task.failure_message
        task.save(
            update_fields=(
                "status",
                "current_stage",
                "failure_code",
                "failure_message",
                "progress_message",
                "updated_at",
            )
        )
        return task

    _persist_result(task, result, image_bytes)
    transition_task(
        task,
        GenerationStatus.AWAITING_CONFIRMATION,
        stage="analysis_complete",
        message="图片分析完成，请确认主体和推荐设置。",
    )
    return task
