from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import RegistrationForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect("creation:upload")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.create(user=user)
        login(request, user)
        return redirect("creation:upload")
    return render(request, "accounts/register.html", {"form": form})
