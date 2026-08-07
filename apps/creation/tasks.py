import logging

from celery import shared_task
from django.utils import timezone

from apps.memberships.services import consume_generation, release_generation

from .analysis import execute_analysis_task
from .models import GenerationStatus, GenerationTask
from .services import generate_basic_pattern
from .state import transition_task

logger = logging.getLogger(__name__)

MAX_AUTOMATIC_ATTEMPTS = 2


def execute_generation_task(task_id: str) -> GenerationTask:
    task = GenerationTask.objects.select_related("settings", "result_version").get(pk=task_id)

    for attempt in range(task.retry_count, MAX_AUTOMATIC_ATTEMPTS):
        task.refresh_from_db()
        if task.status == GenerationStatus.QUOTA_RESERVED:
            transition_task(
                task, GenerationStatus.QUEUED, stage="queued", message="任务已进入队列。"
            )
        if task.status == GenerationStatus.QUEUED:
            transition_task(
                task,
                GenerationStatus.GENERATING,
                stage="preparing",
                message="正在准备图片。",
            )

        try:
            if task.result_version_id is None:
                generate_basic_pattern(task, task.settings)
                task.refresh_from_db()
            consume_generation(task)
            task.completed_at = timezone.now()
            task.save(update_fields=("completed_at", "updated_at"))
            return task
        except Exception as exc:
            logger.exception("Generation attempt failed", extra={"task_id": str(task.pk)})
            task.refresh_from_db()
            task.retry_count = attempt + 1
            task.failure_code = type(exc).__name__
            task.failure_message = str(exc)[:500]
            if attempt + 1 < MAX_AUTOMATIC_ATTEMPTS:
                task.status = GenerationStatus.QUEUED
                task.current_stage = "automatic_retry"
                task.progress_message = "第一次结果未达到要求，系统正在免费优化。"
                task.save(
                    update_fields=(
                        "retry_count",
                        "failure_code",
                        "failure_message",
                        "status",
                        "current_stage",
                        "progress_message",
                        "updated_at",
                    )
                )
                continue

            release_generation(task)
            task.status = GenerationStatus.FAILED
            task.current_stage = "failed"
            task.progress_message = "本次生成未完成，预留张数已经释放。"
            task.completed_at = timezone.now()
            task.save(
                update_fields=(
                    "retry_count",
                    "failure_code",
                    "failure_message",
                    "status",
                    "current_stage",
                    "progress_message",
                    "completed_at",
                    "updated_at",
                )
            )
            return task

    return task


@shared_task(name="creation.run_generation_task")
def run_generation_task(task_id: str) -> str:
    return str(execute_generation_task(task_id).pk)


@shared_task(name="creation.run_analysis_task")
def run_analysis_task(task_id: str) -> str:
    return str(execute_analysis_task(task_id).pk)
