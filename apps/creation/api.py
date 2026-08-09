from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.memberships.services import InsufficientGenerationQuota, reserve_generation

from .models import GenerationStatus, GenerationTask
from .tasks import run_generation_task


def _accepted_response(task, *, idempotent: bool) -> JsonResponse:
    return JsonResponse(
        {
            "task_id": str(task.pk),
            "status": task.status,
            "status_url": f"/create/{task.pk}/status/",
            "progress_url": f"/create/{task.pk}/progress/",
            "idempotent": idempotent,
        },
        status=202,
    )


@require_POST
def confirm_generation_task(request, task_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "请先登录后再确认生成。"}, status=401)

    task = GenerationTask.objects.filter(pk=task_id, user=request.user).first()
    if task is None:
        return JsonResponse({"detail": "未找到这项生成任务。"}, status=404)

    pending_statuses = {
        GenerationStatus.QUOTA_RESERVED,
        GenerationStatus.QUEUED,
        GenerationStatus.GENERATING,
        GenerationStatus.VALIDATING,
    }
    if task.status in pending_statuses:
        return _accepted_response(task, idempotent=True)
    if task.status != GenerationStatus.AWAITING_CONFIRMATION:
        return JsonResponse({"detail": "当前任务不能再次确认生成。"}, status=409)
    if not hasattr(task, "settings"):
        return JsonResponse({"detail": "请先在页面完成图纸参数设置。"}, status=409)

    try:
        reserve_generation(task)
    except InsufficientGenerationQuota as exc:
        return JsonResponse({"detail": str(exc)}, status=409)

    run_generation_task.delay(str(task.pk))
    return _accepted_response(task, idempotent=False)
