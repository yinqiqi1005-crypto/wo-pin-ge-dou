from django.urls import path

from . import views

app_name = "creation"

urlpatterns = [
    path("", views.upload, name="upload"),
    path("<uuid:task_id>/analysis/", views.analysis, name="analysis"),
    path("<uuid:task_id>/settings/", views.settings, name="settings"),
    path("<uuid:task_id>/result/", views.result, name="result"),
    path("<uuid:task_id>/save/", views.save_pattern, name="save"),
]
