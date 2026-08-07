import uuid

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
    readonly_fields = ("used_count", "reserved_count", "starts_at", "ends_at")

    def save_model(self, request, obj, form, change):
        previous_limit = None
        if change:
            previous_limit = type(obj).objects.get(pk=obj.pk).total_limit
        super().save_model(request, obj, form, change)
        if previous_limit is not None and previous_limit != obj.total_limit:
            GenerationQuotaLedger.objects.create(
                quota_period=obj,
                event="adjust",
                amount=abs(obj.total_limit - previous_limit),
                idempotency_key=f"admin-adjust:{obj.pk}:{uuid.uuid4().hex}",
                reason=f"管理员调整周期张数：{previous_limit} → {obj.total_limit}",
                created_by=request.user,
            )


@admin.register(GenerationQuotaLedger)
class GenerationQuotaLedgerAdmin(admin.ModelAdmin):
    list_display = ("quota_period", "event", "amount", "task_reference", "created_at")
    list_filter = ("event",)
    search_fields = ("idempotency_key", "task_reference")
