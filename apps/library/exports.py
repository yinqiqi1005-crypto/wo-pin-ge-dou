from django.core.files.base import ContentFile
from django.db import transaction

from apps.creation.services import pattern_making_guidance
from apps.patterns.models import ExportKind, PatternExport
from services.exports import render_pattern_pdf


@transaction.atomic
def get_or_create_export(version, kind):
    existing = PatternExport.objects.filter(version=version, kind=kind).first()
    if existing:
        return existing
    export = PatternExport(version=version, kind=kind)
    if kind == ExportKind.PATTERN_PDF:
        content, page_count, metadata = render_pattern_pdf(
            version, guidance=pattern_making_guidance(version)
        )
        export.page_count = page_count
        export.metadata = metadata
        export.file.save(
            f"pattern-{version.pattern_id}-v{version.version_number}.pdf",
            ContentFile(content),
            save=False,
        )
    else:
        source = version.effect_preview if kind == ExportKind.EFFECT_PNG else version.grid_preview
        with source.open("rb") as image:
            content = image.read()
        suffix = "effect" if kind == ExportKind.EFFECT_PNG else "grid"
        export.metadata = {
            "grid_width": version.grid_data["width"],
            "grid_height": version.grid_data["height"],
            "source": "formal_pattern_version",
        }
        export.file.save(
            f"pattern-{version.pattern_id}-v{version.version_number}-{suffix}.png",
            ContentFile(content),
            save=False,
        )
    export.save()
    return export
