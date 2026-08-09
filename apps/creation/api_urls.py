from django.urls import path

from . import api

urlpatterns = [
    path(
        "generation-tasks/<uuid:task_id>/confirm/",
        api.confirm_generation_task,
        name="generation-task-confirm",
    ),
]
