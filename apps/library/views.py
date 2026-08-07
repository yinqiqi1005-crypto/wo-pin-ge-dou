from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.patterns.models import Pattern


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
    return render(
        request,
        "library/detail.html",
        {"pattern": pattern, "version": pattern.latest_version},
    )
