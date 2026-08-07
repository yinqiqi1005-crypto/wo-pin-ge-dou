import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, override_settings
from PIL import Image
from pypdf import PdfReader

from apps.creation.services import create_generation_task
from apps.memberships.admin import GenerationQuotaPeriodAdmin
from apps.memberships.models import GenerationQuotaLedger
from apps.memberships.services import get_or_create_current_quota
from apps.operations.admin import ConfigurationRevisionAdmin
from apps.operations.models import ConfigurationRevision
from apps.patterns.models import ExportKind, PatternExport

pytestmark = pytest.mark.django_db


def uploaded_png(name="export.png"):
    image = Image.new("RGB", (100, 100), (250, 245, 235))
    for y in range(20, 80):
        for x in range(20, 80):
            image.putpixel((x, y), (80, 115, 185))
    output = BytesIO()
    image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.fixture(autouse=True)
def demo_configuration():
    call_command("seed_demo_config", verbosity=0)


@pytest.fixture
def creator(client, django_user_model):
    user = django_user_model.objects.create_user(username="export-user")
    client.force_login(user)
    return client, user


def create_saved_pattern(client, user, *, size=30, colors=12):
    client.post("/create/", {"image": uploaded_png(f"export-{size}.png")})
    task = user.generation_tasks.latest("created_at")
    client.post(
        f"/create/{task.pk}/settings/",
        {"grid_size": size, "color_limit": colors, "background_mode": "keep"},
    )
    task.refresh_from_db()
    client.post(
        f"/create/{task.pk}/save/",
        {"title": f"中文图纸 {size}", "note": "导出测试"},
    )
    return task.result_version.pattern, task.result_version


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m8-media")
def test_png_exports_are_exactly_linked_to_formal_version_files(creator):
    client, user = creator
    pattern, version = create_saved_pattern(client, user)

    effect = client.get(
        f"/patterns/{pattern.pk}/versions/{version.version_number}/export/effect.png/"
    )
    grid = client.get(f"/patterns/{pattern.pk}/versions/{version.version_number}/export/grid.png/")
    effect_bytes = b"".join(effect.streaming_content)
    grid_bytes = b"".join(grid.streaming_content)
    with version.effect_preview.open("rb") as source:
        assert effect_bytes == source.read()
    with version.grid_preview.open("rb") as source:
        assert grid_bytes == source.read()

    exports = PatternExport.objects.filter(version=version)
    assert set(exports.values_list("kind", flat=True)) == {
        ExportKind.EFFECT_PNG,
        ExportKind.GRID_PNG,
    }
    assert exports.get(kind=ExportKind.GRID_PNG).metadata["grid_width"] == 30


@pytest.mark.parametrize(
    ("size", "colors", "minimum_pages"),
    [(30, 12, 3), (50, 24, 6), (70, 36, 6)],
)
@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m8-media")
def test_pdf_for_every_grid_size_is_readable_and_matches_materials(
    creator, size, colors, minimum_pages
):
    client, user = creator
    pattern, version = create_saved_pattern(client, user, size=size, colors=colors)

    response = client.get(
        f"/patterns/{pattern.pk}/versions/{version.version_number}/export/pattern.pdf/"
    )
    pdf_bytes = b"".join(response.streaming_content)
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    export = PatternExport.objects.get(version=version, kind=ExportKind.PATTERN_PDF)

    assert response["Content-Type"] == "application/pdf"
    assert len(reader.pages) == export.page_count
    assert len(reader.pages) >= minimum_pages
    assert f"中文图纸 {size}" in text
    assert str(version.total_beads) in text
    assert sum(version.material_counts.values()) == version.total_beads
    for page in reader.pages:
        assert float(page.mediabox.width) > 500
        assert float(page.mediabox.height) > 800
    assert export.metadata["font"] in {"WPD-CJK", "STSong-Light"}
    renderer = shutil.which("pdftoppm")
    assert renderer is not None, "PDF visual acceptance requires Poppler's pdftoppm."
    with TemporaryDirectory() as directory:
        pdf_path = Path(directory) / "pattern.pdf"
        output_prefix = Path(directory) / "rendered"
        pdf_path.write_bytes(pdf_bytes)
        subprocess.run(
            [renderer, "-png", "-f", "1", "-singlefile", str(pdf_path), str(output_prefix)],
            check=True,
            capture_output=True,
        )
        with Image.open(output_prefix.with_suffix(".png")) as rendered:
            assert rendered.width >= 1000
            assert rendered.height >= 1500


@override_settings(MEDIA_ROOT="/tmp/wo-pin-ge-dou-m8-media")
def test_rename_soft_delete_and_export_are_owner_isolated(creator, django_user_model):
    client, user = creator
    pattern, version = create_saved_pattern(client, user)
    response = client.post(
        f"/patterns/{pattern.pk}/update/",
        {"title": "新名称", "note": "新备注"},
    )
    pattern.refresh_from_db()

    assert response.status_code == 302
    assert (pattern.title, pattern.note) == ("新名称", "新备注")

    stranger = django_user_model.objects.create_user(username="export-stranger")
    client.force_login(stranger)
    export_url = f"/patterns/{pattern.pk}/versions/{version.version_number}/export/pattern.pdf/"
    assert client.get(export_url).status_code == 404

    client.force_login(user)
    client.post(f"/patterns/{pattern.pk}/delete/")
    pattern.refresh_from_db()
    assert pattern.deleted_at is not None
    assert client.get(f"/patterns/{pattern.pk}/").status_code == 404
    assert client.get(export_url).status_code == 404
    assert pattern.versions.count() == 1


def test_regular_user_cannot_enter_operations_admin(creator):
    client, _ = creator

    response = client.get("/admin/")

    assert response.status_code == 302
    assert response.url.startswith("/admin/login/")


def test_superuser_can_enter_operations_admin(client, django_user_model):
    operator = django_user_model.objects.create_superuser(username="admin-access")
    client.force_login(operator)

    response = client.get("/admin/")

    assert response.status_code == 200
    assert "站点管理" in response.content.decode()


def test_admin_quota_adjustment_creates_audited_ledger(django_user_model):
    operator = django_user_model.objects.create_superuser(username="quota-admin")
    user = django_user_model.objects.create_user(username="quota-target")
    quota = get_or_create_current_quota(user)
    quota.total_limit += 5
    request = RequestFactory().post("/admin/memberships/generationquotaperiod/")
    request.user = operator
    model_admin = GenerationQuotaPeriodAdmin(type(quota), admin.site)

    model_admin.save_model(request, quota, form=None, change=True)

    ledger = GenerationQuotaLedger.objects.get(event="adjust")
    assert ledger.amount == 5
    assert ledger.created_by == operator
    assert "10 → 15" in ledger.reason


def test_admin_configuration_edit_creates_new_revision(django_user_model):
    operator = django_user_model.objects.create_superuser(username="config-operator")
    original = ConfigurationRevision.objects.get(
        namespace="quality", key="generation_policy", version=1
    )
    original.value["generation_max_attempts"] = 3
    request = RequestFactory().post("/admin/operations/configurationrevision/")
    request.user = operator
    form = type("ChangedForm", (), {"changed_data": ["value"]})()
    model_admin = ConfigurationRevisionAdmin(ConfigurationRevision, admin.site)

    model_admin.save_model(request, original, form=form, change=True)

    revisions = ConfigurationRevision.objects.filter(
        namespace="quality", key="generation_policy"
    ).order_by("version")
    assert list(revisions.values_list("version", flat=True)) == [1, 2]
    assert revisions.last().created_by == operator


def test_running_task_keeps_all_configuration_snapshots(django_user_model):
    user = django_user_model.objects.create_user(username="all-config-snapshot")
    task, _ = create_generation_task(user=user, idempotency_key="all-config")
    options = ConfigurationRevision.objects.get(
        namespace="generation", key="enabled_options", version=1
    )
    options.value["grid_sizes"] = [30]
    options.save(update_fields=("value",))

    assert task.configuration_snapshot["generation"]["enabled_options"]["grid_sizes"] == [
        30,
        50,
        70,
    ]
    assert (
        task.configuration_snapshot["quality"]["generation_policy"]["generation_max_attempts"] == 2
    )
