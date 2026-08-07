from django.contrib import admin

from .models import Palette, PaletteColor, Pattern, PatternVersion


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
    list_display = ("title", "owner", "is_saved", "created_at", "updated_at")
    list_filter = ("is_saved",)
    search_fields = ("title", "owner__username")


@admin.register(PatternVersion)
class PatternVersionAdmin(admin.ModelAdmin):
    list_display = ("pattern", "version_number", "parent_version", "created_at")
    search_fields = ("pattern__title", "pattern__owner__username")
