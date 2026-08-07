from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction

from apps.memberships.models import MembershipPlan, MembershipSubscription
from apps.operations.models import ConfigurationRevision
from apps.patterns.models import Pattern, PatternVersion
from services.image_processing import (
    apply_basic_background,
    create_pattern,
    render_effect_preview,
    render_grid_preview,
)
from services.image_processing.normalize import load_normalized_image

from .models import (
    GenerationMode,
    GenerationSettings,
    GenerationStatus,
    GenerationTask,
)

User = get_user_model()


@transaction.atomic
def create_generation_task(
    *, user: User, idempotency_key: str, mode: str = GenerationMode.BASIC
) -> tuple[GenerationTask, bool]:
    existing = GenerationTask.objects.filter(
        user=user,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        return existing, False

    subscription = (
        MembershipSubscription.objects.select_related("plan")
        .filter(user=user, is_active=True)
        .first()
    )
    if subscription:
        plan = subscription.plan
    else:
        plan = MembershipPlan.objects.get(level="registered", is_active=True)

    model_route = (
        ConfigurationRevision.objects.filter(
            namespace="model_routes", key="analysis", is_active=True
        )
        .order_by("-version")
        .values_list("value", flat=True)
        .first()
        or {}
    )
    task = GenerationTask.objects.create(
        user=user,
        idempotency_key=idempotency_key,
        mode=mode,
        configuration_snapshot={
            "membership": plan.snapshot(),
            "model_routes": {"analysis": model_route},
        },
    )
    return task, True


def _image_content(image, *, name: str) -> ContentFile:
    output = BytesIO()
    image.save(output, format="PNG")
    return ContentFile(output.getvalue(), name=name)


def pattern_making_guidance(version: PatternVersion) -> dict:
    size = version.grid_data.get("width", 50)
    color_count = len(version.material_counts)
    if size <= 30 and color_count <= 12:
        difficulty = "入门"
        advice = "建议先从轮廓开始，再按颜色编号由深到浅填充。"
    elif size >= 70 or color_count > 24:
        difficulty = "进阶"
        advice = "建议分区制作并逐区核对坐标，完成一块后再熨烫拼接。"
    else:
        difficulty = "适中"
        advice = "建议从主体中心向外制作，每完成一行核对一次编号。"
    return {"difficulty": difficulty, "advice": advice}


@transaction.atomic
def generate_basic_pattern(task: GenerationTask, settings: GenerationSettings) -> PatternVersion:
    if not task.input_image:
        raise ValueError("Generation task has no input image.")

    task.current_stage = "pattern_conversion"
    task.progress_message = "正在生成正式拼豆图纸。"
    task.save(update_fields=("current_stage", "progress_message", "updated_at"))

    with task.input_image.open("rb") as source:
        normalized = load_normalized_image(source)
    prepared = apply_basic_background(normalized, mode=settings.background_mode)
    prepared_source = BytesIO()
    prepared.save(prepared_source, format="PNG")
    prepared_source.seek(0)
    result = create_pattern(
        prepared_source,
        size=settings.grid_size,
        color_limit=settings.color_limit,
    )

    effect = render_effect_preview(result.grid, palette=result.palette)
    grid_preview = render_grid_preview(result.grid, palette=result.palette)
    pattern = Pattern.objects.create(owner=task.user, title="未命名图纸", is_saved=False)
    version = PatternVersion(
        pattern=pattern,
        version_number=1,
        grid_data={
            "width": result.grid.width,
            "height": result.grid.height,
            "cells": result.grid.cells,
            "palette": result.palette.code,
        },
        material_counts=result.material_counts,
        settings_snapshot={
            "grid_size": settings.grid_size,
            "color_limit": settings.color_limit,
            "background_mode": settings.background_mode,
        },
        validation_result={"technical": "passed"},
    )
    source_extension = task.input_image.name.rsplit(".", 1)[-1].lower()
    with task.input_image.open("rb") as source:
        source_content = ContentFile(source.read())
    version.source_image.save(
        f"task-{task.pk}-source.{source_extension}",
        source_content,
        save=False,
    )
    version.effect_preview.save(
        f"task-{task.pk}-effect.png",
        _image_content(effect, name="effect.png"),
        save=False,
    )
    version.grid_preview.save(
        f"task-{task.pk}-grid.png",
        _image_content(grid_preview, name="grid.png"),
        save=False,
    )
    version.save()

    task.status = GenerationStatus.SUCCEEDED
    task.result_version = version
    task.current_stage = "completed"
    task.progress_message = "图纸生成完成。"
    task.save(
        update_fields=(
            "status",
            "result_version",
            "current_stage",
            "progress_message",
            "updated_at",
        )
    )
    return version
