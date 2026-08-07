from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from apps.creation.access import GUEST_SESSION_KEY
from apps.creation.models import GenerationTask
from apps.patterns.models import Pattern

from .forms import RegistrationForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect("creation:upload")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.create(user=user)
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
