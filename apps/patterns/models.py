from django.conf import settings
from django.db import models


class Palette(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    version = models.CharField(max_length=40, default="1")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.name


class PaletteColor(models.Model):
    palette = models.ForeignKey(Palette, on_delete=models.CASCADE, related_name="colors")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=80)
    red = models.PositiveSmallIntegerField()
    green = models.PositiveSmallIntegerField()
    blue = models.PositiveSmallIntegerField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "code")
        constraints = [
            models.UniqueConstraint(fields=("palette", "code"), name="unique_palette_color_code")
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.red, self.green, self.blue


class Pattern(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patterns",
    )
    title = models.CharField(max_length=120)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return self.title

    @property
    def latest_version(self):
        return self.versions.order_by("-version_number").first()


class PatternVersion(models.Model):
    pattern = models.ForeignKey(Pattern, on_delete=models.CASCADE, related_name="versions")
    parent_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_versions",
    )
    version_number = models.PositiveIntegerField()
    source_image = models.ImageField(upload_to="patterns/source/%Y/%m/", blank=True)
    creative_base_image = models.ImageField(upload_to="patterns/base/%Y/%m/", blank=True)
    effect_preview = models.ImageField(upload_to="patterns/effect/%Y/%m/", blank=True)
    grid_preview = models.ImageField(upload_to="patterns/grid/%Y/%m/", blank=True)
    grid_data = models.JSONField(default=dict)
    material_counts = models.JSONField(default=dict)
    settings_snapshot = models.JSONField(default=dict)
    validation_result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pattern", "version_number")
        constraints = [
            models.UniqueConstraint(
                fields=("pattern", "version_number"),
                name="unique_pattern_version_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.pattern} · v{self.version_number}"

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        if self.parent_version and self.parent_version.pattern_id != self.pattern_id:
            raise ValidationError("父版本必须属于同一个作品。")
