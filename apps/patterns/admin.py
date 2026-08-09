from django.contrib import admin

from .models import (
    DefaultPatternCategory,
    Palette,
    PaletteColor,
    Pattern,
    PatternCategory,
    PatternExport,
    PatternVersion,
)


class PaletteColorInline(admin.TabularInline):
    model = PaletteColor
    extra = 0


@admin.register(Palette)
class PaletteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "version", "is_active", "is_default")
    list_filter = ("is_active", "is_default")
    inlines = (PaletteColorInline,)


@admin.register(Pattern)
class PatternAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "category",
        "is_saved",
        "deleted_at",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_saved", "deleted_at")


@admin.register(DefaultPatternCategory)
class DefaultPatternCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort_order", "is_fallback", "is_active")
    list_editable = ("sort_order", "is_fallback", "is_active")


@admin.register(PatternCategory)
class PatternCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "sort_order", "is_fallback")
    list_filter = ("is_fallback",)
    search_fields = ("title", "owner__username")


@admin.register(PatternVersion)
class PatternVersionAdmin(admin.ModelAdmin):
    list_display = ("pattern", "version_number", "parent_version", "created_at")
    search_fields = ("pattern__title", "pattern__owner__username")


@admin.register(PatternExport)
class PatternExportAdmin(admin.ModelAdmin):
    list_display = ("version", "kind", "page_count", "created_at")
    list_filter = ("kind",)
