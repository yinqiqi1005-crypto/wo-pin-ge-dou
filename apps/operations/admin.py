from django.contrib import admin
from django.db.models import Max

from .models import ConfigurationRevision


@admin.register(ConfigurationRevision)
class ConfigurationRevisionAdmin(admin.ModelAdmin):
    list_display = ("namespace", "key", "version", "is_active", "created_by", "created_at")
    list_filter = ("namespace", "is_active")
    search_fields = ("namespace", "key")
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if change and set(form.changed_data) - {"created_by"}:
            latest = (
                ConfigurationRevision.objects.filter(
                    namespace=obj.namespace, key=obj.key
                ).aggregate(value=Max("version"))["value"]
                or 0
            )
            obj.pk = None
            obj.version = latest + 1
        obj.created_by = request.user
        super().save_model(request, obj, form, False if obj.pk is None else change)
