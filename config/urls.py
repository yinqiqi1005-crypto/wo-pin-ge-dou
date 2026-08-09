from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("membership/", include("apps.memberships.urls")),
    path("create/", include("apps.creation.urls")),
    path("patterns/", include("apps.library.urls")),
    path("", include("apps.core.urls")),
]

if settings.SERVE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
