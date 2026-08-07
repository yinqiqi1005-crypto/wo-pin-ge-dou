from django.contrib import admin

from .models import (
    Feature,
    GenerationQuotaLedger,
    GenerationQuotaPeriod,
    MembershipPlan,
    MembershipSubscription,
)


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "generation_limit", "priority", "is_active")
    list_filter = ("level", "quota_period", "is_active")
    filter_horizontal = ("features",)


@admin.register(MembershipSubscription)
class MembershipSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "starts_at", "ends_at", "is_active")
    list_filter = ("plan", "is_active")
    search_fields = ("user__username",)


@admin.register(GenerationQuotaPeriod)
class GenerationQuotaPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "total_limit",
        "used_count",
        "reserved_count",
        "starts_at",
        "ends_at",
    )
    search_fields = ("user__username",)


@admin.register(GenerationQuotaLedger)
class GenerationQuotaLedgerAdmin(admin.ModelAdmin):
    list_display = ("quota_period", "event", "amount", "task_reference", "created_at")
    list_filter = ("event",)
    search_fields = ("idempotency_key", "task_reference")
