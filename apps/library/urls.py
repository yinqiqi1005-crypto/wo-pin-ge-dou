from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.pattern_list, name="list"),
    path("<int:pattern_id>/", views.pattern_detail, name="detail"),
    path("<int:pattern_id>/update/", views.update_pattern, name="update"),
    path("<int:pattern_id>/delete/", views.delete_pattern, name="delete"),
    path("<int:pattern_id>/restore/", views.restore_pattern, name="restore"),
    path(
        "<int:pattern_id>/versions/<int:version_number>/export/<str:kind>/",
        views.export_version,
        name="export",
    ),
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
