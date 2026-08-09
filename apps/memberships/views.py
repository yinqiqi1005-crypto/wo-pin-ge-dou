from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import MembershipLevel, MembershipPlan
from .services import activate_demo_membership, current_plan_for_user, get_or_create_current_quota


def plans(request):
    active_plans = MembershipPlan.objects.filter(is_active=True).prefetch_related("features")
    current_plan = current_plan_for_user(request.user) if request.user.is_authenticated else None
    return render(
        request,
        "memberships/plans.html",
        {"plans": active_plans, "current_plan": current_plan},
    )


@login_required
def center(request):
    plan = current_plan_for_user(request.user)
    quota = get_or_create_current_quota(request.user)
    return render(request, "memberships/center.html", {"plan": plan, "quota": quota})


@login_required
def upgrade(request, level):
    if request.method != "POST" or level not in {MembershipLevel.PLUS, MembershipLevel.PRO}:
        raise Http404
    plan = get_object_or_404(MembershipPlan, level=level, is_active=True)
    activate_demo_membership(request.user, plan)
    messages.success(request, f"已模拟升级为 {plan.name}，会员权益已生效。")
    return redirect("memberships:center")
