from django.contrib import admin

from .models import GenerationSettings, GenerationTask, ImageAnalysisResult, ModelCallLog


@admin.register(GenerationTask)
class GenerationTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mode", "status", "retry_count", "created_at")
    list_filter = ("mode", "status")
    search_fields = ("id", "user__username", "idempotency_key")


@admin.register(ImageAnalysisResult)
class ImageAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("task", "primary_subject", "quality_level", "suitability_level")


@admin.register(GenerationSettings)
class GenerationSettingsAdmin(admin.ModelAdmin):
    list_display = ("task", "grid_size", "color_limit", "background_mode")


@admin.register(ModelCallLog)
class ModelCallLogAdmin(admin.ModelAdmin):
    list_display = ("task", "capability", "provider", "model_name", "success", "latency_ms")
    list_filter = ("capability", "provider", "success")
