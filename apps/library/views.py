import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render

from apps.creation.advanced import create_parameter_version
from apps.creation.models import AdvancedCreationRequest, GenerationMode
from apps.creation.services import create_generation_task
from apps.creation.tasks import run_advanced_task
from apps.memberships.services import (
    InsufficientGenerationQuota,
    current_plan_for_user,
    reserve_generation,
)
from apps.patterns.models import Pattern

from .forms import OPERATION_FEATURES, AdvancedCreationForm, ParameterAdjustmentForm


@login_required
def pattern_list(request):
    patterns = Pattern.objects.filter(owner=request.user, is_saved=True).prefetch_related(
        "versions"
    )
    return render(request, "library/list.html", {"patterns": patterns})


@login_required
def pattern_detail(request, pattern_id):
    pattern = get_object_or_404(
        Pattern.objects.prefetch_related("versions"),
        pk=pattern_id,
        owner=request.user,
        is_saved=True,
    )
    version_number = request.GET.get("version")
    version = (
        pattern.versions.filter(version_number=version_number).first()
        if version_number and version_number.isdigit()
        else pattern.latest_version
    )
    if version is None:
        version = pattern.latest_version
    return render(
        request,
        "library/detail.html",
        {"pattern": pattern, "version": version, "versions": pattern.versions.all()},
    )


@login_required
def advanced_create(request, pattern_id, version_number):
    pattern = get_object_or_404(Pattern, pk=pattern_id, owner=request.user, is_saved=True)
    source_version = get_object_or_404(pattern.versions, version_number=version_number)
    plan = current_plan_for_user(request.user)
    enabled_features = set(plan.features.filter(is_active=True).values_list("code", flat=True))
    form = AdvancedCreationForm(request.POST or None, enabled_features=enabled_features)
    if request.method == "POST" and form.is_valid():
        required = OPERATION_FEATURES[form.cleaned_data["operation"]]
        if required not in enabled_features:
            form.add_error("operation", "当前会员等级未开通这项高级创作能力。")
        else:
            task, _ = create_generation_task(
                user=request.user,
                idempotency_key=uuid.uuid4().hex,
                mode=GenerationMode.ADVANCED,
            )
            source_field = (
                source_version.creative_base_image
                if source_version.creative_base_image
                else source_version.source_image
            )
            with source_field.open("rb") as source:
                task.input_image.save(
                    f"advanced-{task.pk}.png", ContentFile(source.read()), save=True
                )
            AdvancedCreationRequest.objects.create(
                task=task,
                source_version=source_version,
                operation=form.cleaned_data["operation"],
                instruction=form.cleaned_data["instruction"],
                preserve_content=form.split_items(form.cleaned_data["preserve_content"]),
                editable_content=form.split_items(form.cleaned_data["editable_content"]),
            )
            try:
                reserve_generation(task)
            except InsufficientGenerationQuota as exc:
                form.add_error(None, str(exc))
            else:
                run_advanced_task.delay(str(task.pk))
                return redirect("creation:progress", task_id=task.pk)
    return render(
        request,
        "library/advanced.html",
        {"pattern": pattern, "version": source_version, "form": form, "plan": plan},
    )


@login_required
def adjust_parameters(request, pattern_id, version_number):
    pattern = get_object_or_404(Pattern, pk=pattern_id, owner=request.user, is_saved=True)
    source_version = get_object_or_404(pattern.versions, version_number=version_number)
    initial = source_version.settings_snapshot
    form = ParameterAdjustmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        version = create_parameter_version(source_version=source_version, **form.cleaned_data)
        messages.success(request, "参数调整完成，本次没有使用生成张数。")
        return redirect(f"/patterns/{pattern.pk}/?version={version.version_number}")
    return render(
        request,
        "library/adjust.html",
        {"pattern": pattern, "version": source_version, "form": form},
    )
