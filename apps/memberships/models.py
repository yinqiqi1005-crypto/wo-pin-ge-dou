from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class MembershipLevel(models.TextChoices):
    VISITOR = "visitor", "免费游客"
    REGISTERED = "registered", "注册会员"
    PLUS = "plus", "Plus 会员"
    PRO = "pro", "Pro 会员"


class QuotaPeriodType(models.TextChoices):
    LIFETIME = "lifetime", "一次性"
    MONTHLY = "monthly", "每月"


class FeatureCode(models.TextChoices):
    BASIC_GENERATION = "basic_generation", "基础生成"
    STYLE_TRANSFER = "style_transfer", "风格转换"
    MULTI_SUBJECT = "multi_subject", "多主体处理"
    COMPOSITION = "composition", "构图调整"
    BACKGROUND_CREATION = "background_creation", "背景创作"
    ELEMENT_EDIT = "element_edit", "元素增删"
    LOCAL_EDIT = "local_edit", "局部重绘"
    ADVANCED_GUIDANCE = "advanced_guidance", "高级制作辅助"


class MembershipPlan(models.Model):
    level = models.CharField(max_length=20, choices=MembershipLevel, unique=True)
    name = models.CharField(max_length=80)
    price_display = models.CharField(max_length=80, blank=True)
    quota_period = models.CharField(
        max_length=20,
        choices=QuotaPeriodType,
        default=QuotaPeriodType.MONTHLY,
    )
    generation_limit = models.PositiveIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    allow_advanced_trial = models.BooleanField(default=False)
    features = models.ManyToManyField("Feature", blank=True, related_name="plans")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "id")

    def __str__(self) -> str:
        return self.name

    def has_feature(self, code: str) -> bool:
        return self.features.filter(code=code, is_active=True).exists()

    def snapshot(self) -> dict:
        return {
            "level": self.level,
            "name": self.name,
            "quota_period": self.quota_period,
            "generation_limit": self.generation_limit,
            "priority": self.priority,
            "features": sorted(self.features.filter(is_active=True).values_list("code", flat=True)),
        }


class Feature(models.Model):
    code = models.CharField(max_length=64, choices=FeatureCode, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.name


class MembershipSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership_subscription",
    )
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="subscriptions")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user} · {self.plan}"


class GenerationQuotaPeriod(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generation_quota_periods",
    )
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="quota_periods")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    total_limit = models.PositiveIntegerField()
    used_count = models.PositiveIntegerField(default=0)
    reserved_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "starts_at"),
                name="unique_user_quota_period_start",
            ),
            models.CheckConstraint(
                condition=Q(used_count__gte=0),
                name="quota_used_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(reserved_count__gte=0),
                name="quota_reserved_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(total_limit__gte=F("used_count") + F("reserved_count")),
                name="quota_usage_within_limit",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · 剩余 {self.remaining_count} 张"

    @property
    def remaining_count(self) -> int:
        return self.total_limit - self.used_count - self.reserved_count

    def clean(self) -> None:
        if self.used_count + self.reserved_count > self.total_limit:
            raise ValidationError("已使用和预留张数不能超过周期总张数。")


class QuotaLedgerEvent(models.TextChoices):
    ALLOCATE = "allocate", "发放"
    RESERVE = "reserve", "预留"
    CONSUME = "consume", "使用"
    RELEASE = "release", "释放"
    ADJUST = "adjust", "后台调整"


class GenerationQuotaLedger(models.Model):
    quota_period = models.ForeignKey(
        GenerationQuotaPeriod,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    task_reference = models.UUIDField(null=True, blank=True)
    event = models.CharField(max_length=20, choices=QuotaLedgerEvent)
    amount = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=120, unique=True)
    reason = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quota_adjustments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"{self.get_event_display()} {self.amount} 张"
