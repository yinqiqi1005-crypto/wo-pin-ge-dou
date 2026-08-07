import uuid

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import GenerationSettingsForm, ImageUploadForm, SavePatternForm
from .models import GenerationSettings, GenerationStatus, GenerationTask
from .services import create_generation_task, create_mock_analysis, generate_basic_pattern


def _user_task_or_404(user, task_id):
    return get_object_or_404(
        GenerationTask.objects.select_related("result_version__pattern"),
        pk=task_id,
        user=user,
    )


@login_required
def upload(request):
    form = ImageUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        task, _ = create_generation_task(user=request.user, idempotency_key=uuid.uuid4().hex)
        task.input_image = form.cleaned_data["image"]
        task.status = GenerationStatus.AWAITING_CONFIRMATION
        task.save(update_fields=("input_image", "status", "updated_at"))
        create_mock_analysis(task)
        return redirect("creation:analysis", task_id=task.pk)
    return render(request, "creation/upload.html", {"form": form})


@login_required
def analysis(request, task_id):
    task = _user_task_or_404(request.user, task_id)
    return render(request, "creation/analysis.html", {"task": task, "analysis": task.analysis})


@login_required
def settings(request, task_id):
    task = _user_task_or_404(request.user, task_id)
    recommendations = task.analysis.recommendations
    instance, _ = GenerationSettings.objects.get_or_create(
        task=task,
        defaults={
            "grid_size": recommendations.get("grid_size", 50),
            "color_limit": recommendations.get("color_limit", 24),
            "background_mode": recommendations.get("background_mode", "simplify"),
        },
    )
    form = GenerationSettingsForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        settings_object = form.save()
        generate_basic_pattern(task, settings_object)
        return redirect("creation:result", task_id=task.pk)
    return render(request, "creation/settings.html", {"task": task, "form": form})


@login_required
def result(request, task_id):
    task = _user_task_or_404(request.user, task_id)
    if task.status != GenerationStatus.SUCCEEDED or not task.result_version:
        return redirect("creation:settings", task_id=task.pk)
    return render(
        request,
        "creation/result.html",
        {"task": task, "version": task.result_version},
    )


@login_required
def save_pattern(request, task_id):
    task = _user_task_or_404(request.user, task_id)
    if not task.result_version:
        return redirect("creation:settings", task_id=task.pk)

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
