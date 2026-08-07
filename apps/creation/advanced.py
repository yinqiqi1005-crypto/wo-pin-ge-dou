import logging
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.memberships.services import consume_generation, release_generation
from apps.patterns.models import Pattern, PatternVersion
from services.ai.advanced import (
    ADVANCED_PROMPT_VERSION,
    REVIEW_PROMPT_VERSION,
    get_advanced_provider,
    review_advanced_result,
)
from services.image_processing import (
    apply_basic_background,
    create_pattern,
    render_effect_preview,
    render_grid_preview,
)
from services.image_processing.normalize import load_normalized_image

from .models import GenerationStatus, GenerationTask, ModelCallLog, ModelCapability
from .state import transition_task

logger = logging.getLogger(__name__)
MAX_ADVANCED_ATTEMPTS = 2


def _field_bytes(version):
    field = version.creative_base_image if version.creative_base_image else version.source_image
    if not field:
        raise ValueError("Source version has no reusable image.")
    with field.open("rb") as source:
        return source.read()


def _png_content(image, name):
    output = BytesIO()
    image.save(output, format="PNG")
    return ContentFile(output.getvalue(), name=name)


@transaction.atomic
def create_version_from_image(
    *, source_version, image_bytes, settings_snapshot, validation_result
) -> PatternVersion:
    pattern = Pattern.objects.select_for_update().get(pk=source_version.pattern_id)
    normalized = load_normalized_image(BytesIO(image_bytes))
    prepared = apply_basic_background(
        normalized,
        mode=settings_snapshot.get("background_mode", "simplify"),
    )
    prepared_bytes = BytesIO()
    prepared.save(prepared_bytes, format="PNG")
    result = create_pattern(
        BytesIO(prepared_bytes.getvalue()),
        size=settings_snapshot.get("grid_size", 50),
        color_limit=settings_snapshot.get("color_limit", 24),
    )
    effect = render_effect_preview(result.grid, palette=result.palette)
    grid = render_grid_preview(result.grid, palette=result.palette)
    next_number = (pattern.versions.order_by("-version_number").first().version_number or 0) + 1
    version = PatternVersion(
        pattern=pattern,
        parent_version=source_version,
        version_number=next_number,
        grid_data={
            "width": result.grid.width,
            "height": result.grid.height,
            "cells": result.grid.cells,
            "palette": result.palette.code,
        },
        material_counts=result.material_counts,
        settings_snapshot=settings_snapshot,
        validation_result=validation_result,
    )
    version.source_image.save(
        f"pattern-{pattern.pk}-v{next_number}-source.png",
        ContentFile(image_bytes),
        save=False,
    )
    version.creative_base_image.save(
        f"pattern-{pattern.pk}-v{next_number}-base.png",
        ContentFile(image_bytes),
        save=False,
    )
    version.effect_preview.save(
        f"pattern-{pattern.pk}-v{next_number}-effect.png",
        _png_content(effect, "effect.png"),
        save=False,
    )
    version.grid_preview.save(
        f"pattern-{pattern.pk}-v{next_number}-grid.png",
        _png_content(grid, "grid.png"),
        save=False,
    )
    version.save()
    return version


def create_parameter_version(*, source_version, grid_size, color_limit, background_mode):
    return create_version_from_image(
        source_version=source_version,
        image_bytes=_field_bytes(source_version),
        settings_snapshot={
            "grid_size": grid_size,
            "color_limit": color_limit,
            "background_mode": background_mode,
            "change_type": "parameter",
        },
        validation_result={"technical": "passed", "review": "not_required"},
    )


def execute_advanced_task(task_id: str) -> GenerationTask:
    task = GenerationTask.objects.select_related(
        "advanced_request__source_version__pattern", "quota_period"
    ).get(pk=task_id)
    request = task.advanced_request
    source_bytes = _field_bytes(request.source_version)
    route = task.configuration_snapshot.get("model_routes", {}).get(
        "advanced_creation", {"provider": "mock"}
    )

    if task.status == GenerationStatus.QUOTA_RESERVED:
        transition_task(task, GenerationStatus.QUEUED, stage="queued", message="高级创作已排队。")
    if task.status == GenerationStatus.QUEUED:
        transition_task(
            task,
            GenerationStatus.GENERATING,
            stage="advanced_creation",
            message="正在创作新底图并保留主体特征。",
        )

    max_attempts = max(1, min(route.get("max_attempts", MAX_ADVANCED_ATTEMPTS), 2))
    try:
        provider = get_advanced_provider(route)
        for attempt in range(max_attempts):
            started = timezone.now()
            try:
                result = provider.edit(
                    source_bytes,
                    operation=request.operation,
                    instruction=request.instruction,
                    preserve=request.preserve_content,
                    editable=request.editable_content,
                    region=request.edit_region,
                )
                ModelCallLog.objects.create(
                    task=task,
                    capability=ModelCapability.IMAGE_EDIT,
                    provider=result.provider,
                    model_name=result.model_name,
                    prompt_version=ADVANCED_PROMPT_VERSION,
                    latency_ms=result.latency_ms,
                    success=True,
                    retry_number=attempt,
                )
                review = review_advanced_result(source_bytes, result.image_bytes)
                ModelCallLog.objects.create(
                    task=task,
                    capability=ModelCapability.VISUAL_REVIEW,
                    provider="rules",
                    model_name="identity-review-v1",
                    prompt_version=REVIEW_PROMPT_VERSION,
                    latency_ms=max(1, int((timezone.now() - started).total_seconds() * 1000)),
                    success=review.status in {"passed", "warning"},
                    retry_number=attempt,
                )
                request.review_result = review.model_dump()
                request.save(update_fields=("review_result",))
                if review.status == "retry":
                    continue
                if review.status == "failed":
                    raise ValueError("Advanced visual review failed.")

                settings_snapshot = {
                    **request.source_version.settings_snapshot,
                    "change_type": "content",
                    "operation": request.operation,
                    "instruction": request.instruction,
                }
                version = create_version_from_image(
                    source_version=request.source_version,
                    image_bytes=result.image_bytes,
                    settings_snapshot=settings_snapshot,
                    validation_result={
                        "technical": "passed",
                        "visual_review": review.model_dump(),
                    },
                )
                task.result_version = version
                task.status = GenerationStatus.SUCCEEDED
                task.current_stage = "completed"
                task.progress_message = "高级创作和图纸复查完成。"
                task.completed_at = timezone.now()
                task.retry_count = attempt
                task.save(
                    update_fields=(
                        "result_version",
                        "status",
                        "current_stage",
                        "progress_message",
                        "completed_at",
                        "retry_count",
                        "updated_at",
                    )
                )
                consume_generation(task)
                return task
            except Exception as exc:
                if not ModelCallLog.objects.filter(
                    task=task,
                    capability=ModelCapability.IMAGE_EDIT,
                    retry_number=attempt,
                ).exists():
                    ModelCallLog.objects.create(
                        task=task,
                        capability=ModelCapability.IMAGE_EDIT,
                        provider=route.get("provider", "unknown"),
                        model_name=route.get("model", "unknown"),
                        prompt_version=ADVANCED_PROMPT_VERSION,
                        success=False,
                        retry_number=attempt,
                        error_type=type(exc).__name__,
                    )
                if attempt + 1 < max_attempts:
                    task.retry_count = attempt + 1
                    task.progress_message = "首次高级结果未通过复查，正在免费重试。"
                    task.save(update_fields=("retry_count", "progress_message", "updated_at"))
                    continue
                raise
        raise ValueError("Advanced result did not pass visual review.")
    except Exception as exc:
        logger.exception("Advanced creation failed", extra={"task_id": str(task.pk)})
        release_generation(task)
        task.status = GenerationStatus.FAILED
        task.current_stage = "advanced_failed"
        task.failure_code = type(exc).__name__
        task.failure_message = str(exc)[:500]
        task.progress_message = "高级创作未完成，旧版本已保留，预留张数已经释放。"
        task.completed_at = timezone.now()
        task.save(
            update_fields=(
                "status",
                "current_stage",
                "failure_code",
                "failure_message",
                "progress_message",
                "completed_at",
                "updated_at",
            )
        )
        return task
