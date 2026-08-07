from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("create/", include("apps.creation.urls")),
    path("patterns/", include("apps.library.urls")),
    path("", include("apps.core.urls")),
]
