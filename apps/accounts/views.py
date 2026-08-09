from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from apps.creation.access import GUEST_SESSION_KEY
from apps.creation.models import GenerationTask
from apps.patterns.categories import ensure_user_categories
from apps.patterns.models import Pattern, PatternCategory

from .forms import PatternCategoryForm, ProfileSettingsForm, RegistrationForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect("creation:upload")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.get_or_create(user=user)
        guest_id = request.session.pop(GUEST_SESSION_KEY, None)
        if guest_id:
            GenerationTask.objects.filter(user_id=guest_id).update(user=user)
            Pattern.objects.filter(owner_id=guest_id).update(owner=user)
        login(request, user)
        next_url = request.POST.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)
        return redirect("creation:upload")
    return render(
        request,
        "accounts/register.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


@login_required
def profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    categories = ensure_user_categories(request.user)
    form = ProfileSettingsForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        request.session["wpgd-language"] = form.cleaned_data["preferred_language"]
        messages.success(request, "个人资料与创作偏好已保存。")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "categories": categories.order_by("sort_order", "id"),
            "category_form": PatternCategoryForm(),
        },
    )


@login_required
def add_category(request):
    if request.method != "POST":
        return redirect("accounts:profile")
    form = PatternCategoryForm(request.POST)
    if form.is_valid():
        PatternCategory.objects.create(
            owner=request.user,
            name=form.cleaned_data["name"],
            sort_order=form.cleaned_data["sort_order"] or 999,
        )
        messages.success(request, "分类已添加。")
    else:
        messages.error(request, "分类未添加，请检查名称和排序。")
    return redirect("accounts:profile")


@login_required
def update_category(request, category_id):
    category = get_object_or_404(PatternCategory, pk=category_id, owner=request.user)
    if request.method == "POST":
        form = PatternCategoryForm(request.POST)
        if form.is_valid():
            category.name = form.cleaned_data["name"]
            category.sort_order = form.cleaned_data["sort_order"] or category.sort_order
            try:
                category.save(update_fields=("name", "sort_order", "updated_at"))
            except IntegrityError:
                messages.error(request, "分类名称不能重复。")
            else:
                messages.success(request, "分类已更新。")
    return redirect("accounts:profile")


@login_required
def delete_category(request, category_id):
    category = get_object_or_404(PatternCategory, pk=category_id, owner=request.user)
    if request.method == "POST":
        if category.is_fallback:
            messages.error(request, "“其他”是兜底分类，不能删除。")
        else:
            category.delete()
            messages.success(request, "分类已删除，图纸已移入“其他”。")
    return redirect("accounts:profile")
