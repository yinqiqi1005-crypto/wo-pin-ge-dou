import uuid

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserProfile
from apps.memberships.services import (
    InsufficientGenerationQuota,
    get_or_create_current_quota,
    release_generation,
    reserve_generation,
)

from .access import effective_creation_user
from .forms import (
    GenerationSettingsForm,
    ImageUploadForm,
    SavePatternForm,
    SubjectSelectionForm,
)
from .models import GenerationSettings, GenerationStatus, GenerationTask
from .services import create_generation_task, pattern_making_guidance
from .state import transition_task
from .tasks import run_analysis_task, run_generation_task


def _user_task_or_404(user, task_id):
    return get_object_or_404(
        GenerationTask.objects.select_related("result_version__pattern"),
        pk=task_id,
        user=user,
    )


def upload(request):
    creation_user = effective_creation_user(request)
    form = ImageUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        task, _ = create_generation_task(user=creation_user, idempotency_key=uuid.uuid4().hex)
        task.input_image = form.cleaned_data["image"]
        task.save(update_fields=("input_image", "updated_at"))
        run_analysis_task.delay(str(task.pk))
        return redirect("creation:analysis", task_id=task.pk)
    quota = get_or_create_current_quota(creation_user)
    recent_tasks = GenerationTask.objects.filter(user=creation_user)[:5]
    return render(
        request,
        "creation/upload.html",
        {"form": form, "quota": quota, "recent_tasks": recent_tasks},
    )


def analysis(request, task_id):
    task = _user_task_or_404(effective_creation_user(request), task_id)
    analysis_result = getattr(task, "analysis", None)
    initial = analysis_result.subject_region if analysis_result else None
    subject_form = SubjectSelectionForm(request.POST or None, initial=initial)
    if request.method == "POST" and analysis_result and subject_form.is_valid():
        analysis_result.subject_region = subject_form.cleaned_data
        analysis_result.requires_subject_confirmation = False
        analysis_result.save(
            update_fields=("subject_region", "requires_subject_confirmation", "updated_at")
        )
        GenerationSettings.objects.update_or_create(
            task=task,
            defaults={
                "selected_subject": subject_form.cleaned_data,
                "crop": subject_form.cleaned_data,
                "grid_size": analysis_result.recommendations.get("grid_size", 50),
                "color_limit": analysis_result.recommendations.get("color_limit", 24),
                "background_mode": analysis_result.recommendations.get(
                    "background_mode", "simplify"
                ),
            },
        )
        return redirect("creation:settings", task_id=task.pk)
    return render(
        request,
        "creation/analysis.html",
        {"task": task, "analysis": analysis_result, "subject_form": subject_form},
    )


def settings(request, task_id):
    creation_user = effective_creation_user(request)
    task = _user_task_or_404(creation_user, task_id)
    recommendations = task.analysis.recommendations
    instance, _ = GenerationSettings.objects.get_or_create(
        task=task,
        defaults={
            "grid_size": recommendations.get("grid_size", 50),
            "color_limit": recommendations.get("color_limit", 24),
            "background_mode": recommendations.get("background_mode", "simplify"),
        },
    )
    form = GenerationSettingsForm(
        request.POST or None,
        instance=instance,
        has_subject=task.analysis.subject_count > 0,
        enabled_options=task.configuration_snapshot.get("generation", {}).get("enabled_options"),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        try:
            reserve_generation(task)
        except InsufficientGenerationQuota as exc:
            form.add_error(None, str(exc))
        else:
            run_generation_task.delay(str(task.pk))
            return redirect("creation:progress", task_id=task.pk)
    quota = get_or_create_current_quota(creation_user)
    membership = task.configuration_snapshot.get("membership", {})
    return render(
        request,
        "creation/settings.html",
        {
            "task": task,
            "form": form,
            "quota": quota,
            "membership": membership,
            "features": membership.get("features", []),
        },
    )


def progress(request, task_id):
    task = _user_task_or_404(effective_creation_user(request), task_id)
    return render(request, "creation/progress.html", {"task": task})


def task_status(request, task_id):
    task = _user_task_or_404(effective_creation_user(request), task_id)
    return JsonResponse(
        {
            "status": task.status,
            "stage": task.current_stage,
            "message": task.progress_message,
            "retry_count": task.retry_count,
            "result_url": (
                f"/create/{task.pk}/result/"
                if task.status in {GenerationStatus.SUCCEEDED, GenerationStatus.SAVED}
                else None
            ),
        }
    )


def cancel_task(request, task_id):
    task = _user_task_or_404(effective_creation_user(request), task_id)
    if request.method == "POST" and task.status in {
        GenerationStatus.QUOTA_RESERVED,
        GenerationStatus.QUEUED,
    }:
        release_generation(task)
        transition_task(
            task,
            GenerationStatus.CANCELLED,
            stage="cancelled",
            message="排队任务已取消，预留张数已经释放。",
        )
    return redirect("creation:progress", task_id=task.pk)


def result(request, task_id):
    task = _user_task_or_404(effective_creation_user(request), task_id)
    if task.status != GenerationStatus.SUCCEEDED or not task.result_version:
        return redirect("creation:settings", task_id=task.pk)
    return render(
        request,
        "creation/result.html",
        {
            "task": task,
            "version": task.result_version,
            "guidance": pattern_making_guidance(task.result_version),
        },
    )


def save_pattern(request, task_id):
    creation_user = effective_creation_user(request)
    task = _user_task_or_404(creation_user, task_id)
    if not task.result_version:
        return redirect("creation:settings", task_id=task.pk)
    if UserProfile.objects.filter(user=creation_user, is_guest=True).exists():
        return redirect(f"/accounts/register/?next=/create/{task.pk}/save/")

    pattern = task.result_version.pattern
    form = SavePatternForm(
        request.POST or None,
        initial={"title": pattern.title, "note": pattern.note},
    )
    if request.method == "POST" and form.is_valid():
        pattern.title = form.cleaned_data["title"]
        pattern.note = form.cleaned_data["note"]
        pattern.is_saved = True
        pattern.save(update_fields=("title", "note", "is_saved", "updated_at"))
        task.status = GenerationStatus.SAVED
        task.save(update_fields=("status", "updated_at"))
        return redirect("library:detail", pattern_id=pattern.pk)
    return render(request, "creation/save.html", {"task": task, "pattern": pattern, "form": form})
