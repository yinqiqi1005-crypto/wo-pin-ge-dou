from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.pattern_list, name="list"),
    path("<int:pattern_id>/", views.pattern_detail, name="detail"),
    path(
        "<int:pattern_id>/versions/<int:version_number>/advanced/",
        views.advanced_create,
        name="advanced",
    ),
    path(
        "<int:pattern_id>/versions/<int:version_number>/adjust/",
        views.adjust_parameters,
        name="adjust",
    ),
]
