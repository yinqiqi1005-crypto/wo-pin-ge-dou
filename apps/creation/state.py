from .models import GenerationStatus, GenerationTask

ALLOWED_TRANSITIONS = {
    GenerationStatus.UPLOADED: {GenerationStatus.ANALYZING, GenerationStatus.FAILED},
    GenerationStatus.ANALYZING: {
        GenerationStatus.AWAITING_CONFIRMATION,
        GenerationStatus.FAILED,
    },
    GenerationStatus.AWAITING_CONFIRMATION: {
        GenerationStatus.QUOTA_RESERVED,
        GenerationStatus.FAILED,
    },
    GenerationStatus.QUOTA_RESERVED: {
        GenerationStatus.QUEUED,
        GenerationStatus.CANCELLED,
        GenerationStatus.FAILED,
    },
    GenerationStatus.QUEUED: {
        GenerationStatus.GENERATING,
        GenerationStatus.CANCELLED,
        GenerationStatus.FAILED,
    },
    GenerationStatus.GENERATING: {
        GenerationStatus.QUEUED,
        GenerationStatus.VALIDATING,
        GenerationStatus.SUCCEEDED,
        GenerationStatus.FAILED,
    },
    GenerationStatus.VALIDATING: {
        GenerationStatus.SUCCEEDED,
        GenerationStatus.QUEUED,
        GenerationStatus.FAILED,
    },
    GenerationStatus.SUCCEEDED: {GenerationStatus.SAVED},
    GenerationStatus.SAVED: set(),
    GenerationStatus.FAILED: set(),
    GenerationStatus.CANCELLED: set(),
}


class InvalidTaskTransition(ValueError):
    """Raised when a task attempts an impossible state transition."""


def transition_task(
    task: GenerationTask,
    status: str,
    *,
    stage: str = "",
    message: str = "",
) -> GenerationTask:
    allowed = ALLOWED_TRANSITIONS.get(task.status, set())
    if status not in allowed:
        raise InvalidTaskTransition(f"Cannot transition task from {task.status} to {status}.")
    task.status = status
    task.current_stage = stage
    task.progress_message = message
    task.save(update_fields=("status", "current_stage", "progress_message", "updated_at"))
    return task
