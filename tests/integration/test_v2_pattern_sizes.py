import pytest

from apps.creation.forms import GenerationSettingsForm
from apps.creation.models import GenerationSettings, GenerationTask


@pytest.mark.django_db
def test_v2_pattern_size_uses_width_and_height_without_blocking_face_detail_warning(
    django_user_model,
):
    user = django_user_model.objects.create_user(username="size-owner")
    task = GenerationTask.objects.create(user=user, idempotency_key="v2-size-form")
    settings = GenerationSettings.objects.create(task=task, grid_size=50, color_limit=24)
    form = GenerationSettingsForm(
        {
            "pattern_size": "58x87",
            "color_limit": 24,
            "background_mode": "simplify",
            "face_mode": "face_detail",
        },
        instance=settings,
    )

    assert form.is_valid(), form.errors
    saved = form.save()
    assert (saved.grid_width, saved.grid_height) == (58, 87)
    assert saved.grid_size == 87
    assert saved.face_mode == "face_detail"
