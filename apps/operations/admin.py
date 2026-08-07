from django.contrib import admin

from .models import ConfigurationRevision


@admin.register(ConfigurationRevision)
class ConfigurationRevisionAdmin(admin.ModelAdmin):
    list_display = ("namespace", "key", "version", "is_active", "created_by", "created_at")
    list_filter = ("namespace", "is_active")
    search_fields = ("namespace", "key")
